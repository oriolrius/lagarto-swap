import os
import sys

# FIX-ME : current lagarto-swap use this kind of
# path to load lagarto resources ...
working_dir = os.path.dirname(__file__)
lagarto_dir = os.path.split(working_dir)[0]
lagarto_dir = os.path.join(lagarto_dir, "lagarto")
sys.path.append(lagarto_dir)
from lagartomqtt.plugin import MqttPluginInterface, MqttPluginDropMessage

from datetime import datetime, timedelta
import logging

class TimestampPlugin(MqttPluginInterface):
    name = "Timestamp and ttl pluguin"
    author = ""

    FORMAT = "%Y-%m-%dT%H:%M:%S"

    @classmethod
    def _handle_timestamp(cls, message):
        if "timestamp" not in message:
            date = datetime.now()
            message["timestamp"] = date.strftime(TimestampPlugin.FORMAT)
        else: 
            # check format and fix it
            try:
                # 18 Oct 2013 09:00:00
                date = datetime.strptime(message["timestamp"], "%d %b %Y %H:%M:%S")
            except ValueError, v:
                logging.warning("Timestamp format not expected %s" % message["timestamp"])
                raise v
            message["timestamp"] = date.strftime(TimestampPlugin.FORMAT)

        return date, message

    def incoming(self, message):
        """
        Messages comming from Mqtt topic
        """
        dt, message = TimestampPlugin._handle_timestamp(message)
        if dt is None:
            raise MqttPluginDropMessage("Messages without timestamp are forbidden, dropping")
 
        if "ttl" in message:
            now = datetime.now()
            offset_time = deltatime(0, int(message["ttl"]))
            if now > (dt + offset_time):
                raise MqttPluginDropMessage("Message is out of date, dropping")

        return message

        
    def outgoing(self, message):
        """
        Messages going to Mqtt topic
        """
        dt, message = TimestampPlugin._handle_timestamp(message)
        if dt is None:
            raise MqttPluginDropMessage("Messages without timestamp are forbidden, dropping")
 
        return message
       
