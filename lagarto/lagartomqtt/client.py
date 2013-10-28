#########################################################################
# 
# Copyright (c) 2012 Daniel Berenguer <dberenguer@usapiens.com>
#
# This file is part of the lagarto project.
#
# lagarto  is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# lagarto is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with panLoader; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA
#
#########################################################################
__author__="Pau Freixes"
__date__  ="17 Oct, 2013"
#########################################################################

from lagartoresources import LagartoException, LagartoMessage
from lagartoresources import LagartoEndpoint
from lagartomqtt.plugin import MqttPluginHandle
from lagartomqtt.plugin import MqttPluginHandleException, MqttPluginDropMessage

from swap.protocol.SwapDefs import SwapType

import threading
import json
import os
import time
import datetime
import logging

try:
    import mosquitto
    mqtt_available = True
except ImportError:
    mqtt_available = False
    logging.warning("Module mosquitto seems to be unavailable, disabling mqtt....")


class MqttClient(threading.Thread):
    """
    A MqttClinet class to handle all mqtt protocol
    at Lagarto

    Example of message format sent and received to/from mqtt :
    {
        "direction": "out", 
        "name": "Binary_0", 
        "timestamp": "02 Oct 2013 10:48:35", 
        "value": "off", 
        "location": "SWAP", 
        "type": "bin", 
        "id": "17.11.0"
    }
    """

    # libmosquitto provides thread safe operation.
    # then we could use the native client function stright for
 
    RESUME_TIME = 10  # seconds

    @staticmethod
    def on_publish(mosq, obj, mid):
        pass

    @staticmethod
    def on_message(mosq, obj, msg):
        """
        Callback executed when new message to one topic apears at the mqtt
        channel

        @param obj a MqttClient instance
        @param msg a MosquittoMessage intance
        """
        obj._msg_rcv += 1

        if msg.topic not in obj._subscribed_topics:
            logging.info("Mqtt message from one unknowed topic %s, discarding ...." % msg.topic)
            return

        # topic keeps location and id, message has only a buffer
        location, uid = obj.split_topic(msg.topic)

        try:
            data = json.loads(msg.payload)
            uid_msg = data["id"]
            location_msg = data["location"]
            name_msg = data["name"]
            value_msg = data["value"]
        except Exception, e:
            logging.warning("Error parsing message from mqtt %s" % str(e))
            return

        logging.debug("MQTT msg payload: %s" % str(msg.payload))

        endp = LagartoEndpoint(endp_id=uid, location=location, name=name_msg, value=value_msg)

        try:
            message = obj._plugin_handle.incoming(endp.dumps())
            obj.data_server.set_status([message])
        except MqttPluginDropMessage, e:
            logging.debug("Dropped message from plugin... %s" % str(e))

    def split_topic(self, topic):
        """
        Topic is always /location/measeure/id
        """
        _, location, _, id_ = topic.split("/")
        return location, id_

    def get_topic_name(self, msg, type_of):
        """
        Return a topic name from one swap message
        """
        return "/%s/%s/%s" % (msg["location"], type_of, msg["id"])

    def subscribe(self, endpoint, force=False):
        """
        Try to subscribe to one endpoint mqtt channel 
        """
        if self._client is None:
            raise Exception("MQTT client not set, topic cant be susbcribed")

        topic = self.get_topic_name(endpoint, "action")
        if topic in self._subscribed_topics:
            return

        self._subscribed_topics.append(topic)

        logging.info("MQTT client subscribing at %s" % topic)
        return self._client.subscribe(topic)

    def unsubscribe(self, endpoint, force=False):
        """
        Try to unsubscribe to one endpoint already subscribed at one mqtt channel 
        """
        if self._client is None:
            raise Exception("MQTT client not set, topic cant be unsusbcribed")

        topic = self.get_topic_name(endpoint, "action")
        if topic not in self._subscribed_topics:
            return

        self._subscribed_topics.remove(topic)

        logging.info("MQTT client unsubscribing at %s" % topic)
        return self._client.unsubscribe(topic)


    def publish(self, endpoint):
        """
        Try to publish to one endpoint mqtt channel 
        """
        if self._client is None:
            raise Exception("MQTT client not set, topic cant be published")


        # READ from mosquitto web
        # libmosquitto provides thread safe operation.
        # then we could use the native client function stright for
        topic = self.get_topic_name(endpoint, "measure")
        return self._client.publish(topic, json.dumps(endpoint))


    def handle_swap_message(self, msg_list):
        """
        Send messages to  topics, msg is a list of SwapEndpoint that they
        has changed the value of kind of register
        """
        if not self._client:
            logging.info("Mqtt client is down ? discarding message ....")
            return


        for endpoint in msg_list:
            direction = endpoint["direction"]
            if direction == SwapType.OUTPUT:
                self.subscribe(endpoint, force=False)
            elif direction == SwapType.INPUT:
                try:
                    message = self._plugin_handle.outgoing(endpoint)
                    ret, mid = self.publish(message)
                    if ret != 0:
                        logging.warning("Mqtt publish error %d" % ret)
                    else:
                        self._msg_sent += 1
                except MqttPluginDropMessage, e:
                    logging.info("Dropped message from plugin... %s" % str(e))
            else:
                logging.warning("Mqtt received unuknowed swap type direction %s" % direction)

    def subscribe_all_endpoints(self, force=False, skip_pwrdwn = True):
        """
        Subscribe all endpoints except they are belonging 
        at one pwrdwn mote. Use force to override older
        subscriptions
        """
        for mote in self.data_server.network.motes:
            if skip_pwrdwn and mote.pwrdownmode:
                logging.info("MQTT Mote %d.%d " % (mote.product_id, mote.manufacturer_id) +\
                             "is pwrdwn, waiting sync message for subscribe" )
                continue

            for reg in mote.regular_registers:
                for endp in reg.parameters:
                    direction = endp.direction
                    if direction == SwapType.OUTPUT:
                        self.subscribe(endp.dumps(), force=force)

    def subscribe_endpoint(self, endpoint, force=False):
        """
        Subscribe a endpoint
        """
        direction = endpoint.direction
        if direction == SwapType.OUTPUT:
            self.subscribe(endpoint.dumps(), force=force)
        else:
            logging.info("MQTT subscribe skip INPUT endpoint %s" % endpoint.name)

    def unsubscribe_endpoint(self, endpoint, force=False):
        """
        Unsubscribe a endpoint
        """
        self.unsubscribe(endpoint.dumps(), force=force)


    def run(self):
        """
        Run Mqtt client threaded
        """
        logging.info("Starting Mqtt client ....")
        # connect to server
        self._client = mosquitto.Mosquitto(self.config.client_id, userdata=self)
        self._client.on_message =  MqttClient.on_message
        self._client.on_publish =  MqttClient.on_publish
        self._client.connect(self.config.host,
                             self.config.port)

        self.subscribe_all_endpoints()

        seconds_wait = [ 2**x for x in range(1, 8) ]
        self.running = True
        i = 0
        last_resume = datetime.datetime.now()
        while self.running:
            ret = self._client.loop(timeout=0.2)
            if ret != 0:
                # something is going bad, just try to reconect
                # after one second, it locks this thread
                logging.warning("MQTT client connection broken ... reconecting in %d seconds" % seconds_wait[i])
                time.sleep(seconds_wait[i])
                self._client.reconnect()
                if (i + 1) < len(seconds_wait):
                    i+=1
            elif i != 0:
                logging.info("MQTT client connection raised again ....")
                i = 0
            else:
                now = datetime.datetime.now()
                if now > last_resume + datetime.timedelta(0, MqttClient.RESUME_TIME):
                    resume = "MQTT msg sent: %d, msg rcv: %d" % (self._msg_sent, self._msg_rcv)
                    last_resume = now
                    logging.info(resume)
                    
        self._client.disconnect()
        
    def stop(self):
        """
        Stop mqtt client
        """
        logging.info("Stopping Mqtt client, sent %d msgs ...." % self._msg_sent)
        self.running = False
        time.sleep(0.00001) # relase GIL

    def __init__(self, config_mqtt, data_server=None):
        '''
        Constructor
        
        @param config_mqtt: A MqttConfig instance
        '''
        if mqtt_available is False:
            raise Exception("mosquitto package is not available,",\
                " install it or disable the configuration to don't use it")

        # we want to use only thread safe clients > 1.0
        # Client doesnt have a real version atribute, we
        # have to figure out just getting one kind of attribute
        if not hasattr(mosquitto, "CONNACK_ACCEPTED"):
            raise Exception("Mosquitto client version is not supported, upgrade it or disable it")
 

        self.config = config_mqtt
        self.data_server = data_server
        self._msg_sent = 0
        self._msg_rcv = 0
        self._subscribed_topics = []
        self._plugin_handle = MqttPluginHandle()
        threading.Thread.__init__(self)

