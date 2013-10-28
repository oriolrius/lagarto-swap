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
__author__="Daniel Berenguer"
__date__  ="$Jan 26, 2012$"
#########################################################################

from lagartoconfig import XmlLagarto
from lagartohttp import LagartoHttpServer
from lagartoresources import LagartoException, LagartoMessage
from lagartoresources import LagartoEndpoint
from lagartomqtt.client import MqttClient

from swap.protocol.SwapDefs import SwapType, SwapState

import httplib
import threading
import json
import socket
import os
import time
import datetime
import logging

try:
    import zmq
    zmq_available = True
except ImportError:
    zmq_available = False




class LagartoProcess(object):
    """
    Geenric Lagarto process class
    """
    def get_status(self, endpoints):
        """
        Return network status as a list of endpoints in JSON format
        Method to be overriden by subclass
        
        @param endpoints: list of endpoints being queried
        
        @return list of endpoints in JSON format
        """
        return None


    def set_status(self, endpoints):
        """
        Set endpoint status
        Method to be overriden by subclass
        
        @param endpoints: list of endpoints in JSON format
        
        @return list of endpoints being controlled, with new values
        """
        return None


    def http_command_received(self, command, params):
        """
        Process command sent from HTTP server. Method to be overrided by data server.
        Method to be overriden by subclass
        
        @param command: command string
        @param params: dictionary of parameters
        
        @return True if command successfukky processed by server.
        Return False otherwise
        """
        return False
    

    def _get_local_ip_address(self):
        """
        Get local IP address
        
        @return local IP address
        """
        ipaddr = socket.gethostbyname(socket.gethostname())
        if ipaddr.startswith("127.0"):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("1.1.1.1", 8000))
                ipaddr = s.getsockname()[0]
                s.close()
            except:
                pass
 
        return ipaddr


    def stop(self):
        """
        Stop HTTP server
        """
        self.http_server.stop()


    def __init__(self, working_dir):
        '''
        Constructor
        
        @param working_dir: Working directory
        '''
        cfg_path = os.path.join(working_dir, "config", "lagarto.xml")
        # Read configuration file       
        self.config = XmlLagarto(cfg_path)
        
        ## Local IP address
        address = self._get_local_ip_address()
        # Save IP address in config file
        if self.config.address != address:
            self.config.address = address
            self.config.save()

        # HTTP server
        self.http_server = LagartoHttpServer(self, self.config, working_dir)
        self.http_server.start()


class PeriodicHeartBeat(threading.Thread):
    """
    Periodic transmission of Lagarto server heart beat
    """
    def run(self):
        """
        Start timer
        """
        while True:
            self.send_hbeat()
            time.sleep(60)
                      
    
    def __init__(self, send_hbeat):
        """
        Constructor
        
        @param send_hbeat: Heart beat transmission method
        """
        threading.Thread.__init__(self)
        # Configure thread as daemon
        self.daemon = True
        # Heart beat transmission method
        self.send_hbeat = send_hbeat



class LagartoServer(LagartoProcess):
    """
    Lagarto server class
    """
    def new_mote_detected(self, endp):
        """
        Broadcast new mote detected
        """
        pass

    def new_endpoint_detected(self, endp):
        """
        Broadcast new endpoint detected
        """
        self.publish_lock.acquire()
        try:
            if self.mqtt_client:
                self.mqtt_client.subscribe_endpoint(endp)
        finally:
            self.publish_lock.release()

    def mote_state_changed(self, mote):
        """
        Broadcast a mote state has changed
        """
        if not self.mqtt_client:
            return # nothing to do
        if mote.state == SwapState.SYNC:
            f = self.mqtt_client.subscribe_endpoint
        elif mote.state == SwapState.RXOFF:
            f = self.mqtt_client.unsubscribe_endpoint
        else:
            return # nothing to do

        for reg in mote.regular_registers:
            for endp in reg.parameters:
                self.publish_lock.acquire()
                try:
                    f(endp)
                finally:
                    self.publish_lock.release()

    def mote_address_changed(self, mote):
        # nothing to do
        pass
 
    def publish_status(self, status_data=None):
        """
        Broadcast network status (collection of endpoint data)
        
        @param status_data list of network status to be transmitted
        """
        self.publish_lock.acquire()
        try:
            http_server = self.config.address + ":" + str(self.config.httpport)
            lagarto_msg = LagartoMessage(proc_name=self.config.procname, http_server=http_server, status=status_data)
            msg = json.dumps(lagarto_msg.dumps())

            # send to zmq
            if self.pub_socket:
                self.pub_socket.send(msg)

            # mqtt 
            if self.mqtt_client and status_data:
                self.mqtt_client.handle_swap_message(status_data)
            elif self.mqtt_client and not status_data:
                # probably HBEAT message, skipping it at mqtt level
                pass
        finally:
            self.publish_lock.release()
                

    def stop(self):
        """
        Stop lagarto server
        """
        # Close Mqtt client
        if self.mqtt_client is not None:
            self.mqtt_client.stop()

        # Close ZeroMQ socket
        if self.pub_socket is not None:
            self.pub_socket.setsockopt(zmq.LINGER, 0)
            self.pub_socket.close()
        
        # Close HTTP server
        LagartoProcess.stop(self)

       


    def __init__(self, working_dir):
        '''
        Constructor
        
        @param working_dir: Working directory
        '''
        self.publish_lock = threading.Lock()

        LagartoProcess.__init__(self, working_dir)
        

        # ZMQ PUB socket
        self.pub_socket = None
        if self.config.broadcast is not None:
            if zmq_available is False:
                raise Exception(" package is not available,",\
                    " install it or disable the configuration to don't use it")

            context = zmq.Context()
            self.pub_socket = context.socket(zmq.PUB)
            
            # Bind/connect socket
            try:
                # Try binding socket first
                if self.pub_socket.bind(self.config.broadcast) == -1:
                    raise LagartoException("Unable to bind zmq pub socket")
                else:
                    logging.info("ZMQ PUB socket binded to ", self.config.broadcast)
            except zmq.ZMQError as ex:
                try:
                    # Now try connecting to the socket            
                    if self.pub_socket.connect(self.config.broadcast) == -1:
                        raise LagartoException("Unable to connect to zmq pub socket")
                    else:
                        logging.info("ZMQ PUB socket connected to", self.config.broadcast)
                except zmq.ZMQError as ex:
                    raise LagartoException("Unable to establish connection with zmq pub socket: " + str(ex))
            
            
            # Heart beat transmission thread
            self.hbeat_process = PeriodicHeartBeat(self.publish_status)
            self.hbeat_process.start()

        self.mqtt_client = None
        if self.config.mqtt is not None:
            self.mqtt_client = MqttClient(self.config.mqtt, data_server=self)
            self.mqtt_client.start()


class LagartoClient(threading.Thread, LagartoProcess):
    '''
    Lagarto client class
    '''
    def notify_status(self, event):
        """
        Notify status to the master application (callback)
        To be implemented by subclass
        
        @param event: message received from publisher in JSON format
        """
        pass
    
    
    def run(self):
        """
        Run server thread
        """
        while self.running:           
            try:
                # Any broadcasted message from a lagarto server?
                event = self.sub_socket.recv(flags=zmq.NOBLOCK)
            except:
                event = None
                pass
            
            # Process event
            if event is not None:
                self._process_event(event)
            time.sleep(0.01)
        
        logging.info("Stopping lagarto client...")
            
            
    def stop(self):
        """
        Stop lagarto client
        """        
        self.running = False
        
        # Close ZeroMQ socket
        self.sub_socket.setsockopt(zmq.LINGER, 0)
        self.sub_socket.close()
        
        # Close HTTP server
        LagartoProcess.stop(self)
        
        
    def _process_event(self, event):
        """
        Process lagarto event
        
        @param event: event packet to be processed
        """
        event_data = json.loads(event)
        if "lagarto" in event_data:
            event_data = event_data["lagarto"]
            if "httpserver" in event_data:
                # HTTP server not in list?
                if event_data["procname"] not in self.http_servers:
                    self.http_servers[event_data["procname"]] = event_data["httpserver"]
                
            if "status" in event_data:
                logging.debug("STATUS received from %s" %  event_data["procname"])
                self.notify_status(event_data)
            else:
                logging.debug("HBEAT received from" % event_data["procname"])
                                             
        
    def request_status(self, procname, req):
        """
        Query/command network/endpoint status from server
        
        @param procname: name of the process to be queried
        @param req: queried/controlled endpoints
        
        @return status
        """
        if len(req) > 0:
            control = False
            if "value" in req[0]:
                control = True
            
            cmd_list = []
            for endp in req:
                if endp["location"] is not None and endp["name"] is not None:
                    cmd = "location=" + endp["location"] + "&" + "name=" + endp["name"]
                elif endp["id"] is not None:
                    cmd = "id=" + endp["id"]
                else:
                    raise LagartoException("Insufficient data to identify endpoint")
                
                if control:
                    cmd += "&value=" + endp["value"]
                cmd_list.append(cmd)

            if procname in self.http_servers:
                try:
                    conn = httplib.HTTPConnection(self.http_servers[procname], timeout=5)
                    conn.request("GET", "/values/?" + "&".join(cmd_list))
                    response = conn.getresponse()
                    if response.reason == "OK":
                        status_response = json.loads(response.read())
                        status_msg = LagartoMessage(status_response)
         
                        return status_msg.status
                except:
                    raise LagartoException("Unable to get response from HTTP server")

        return None
    


    def get_servers(self):
        """
        Serialize list of lagarto servers in JSON format
        """
        return {"http_servers": self.http_servers}
            

    def get_endpoints(self, server):
        """
        Serialize network data from lagarto server
        
        @param server: lagarto http address:port
        
        @return network data in JSON format
        """
        try:
            conn = httplib.HTTPConnection(server, timeout=5)
            conn.request("GET", "/values")
            response = conn.getresponse()
            if response.reason == "OK":
                return json.loads(response.read())
        except:
            raise LagartoException("Unable to get response from HTTP server")

        return None


    def set_endpoint(self, endpoint):
        """
        Set endpoint value
        
        @param endpoint: lagarto endpoint
        
        @return network data in JSON format
        """
        if endpoint.procname is None:
            return None

        if endpoint.procname not in self.http_servers:
            return None

        server = self.http_servers[endpoint.procname]
        
        try:
            conn = httplib.HTTPConnection(server, timeout=20)
            if endpoint.id is not None:
                conn.request("GET", "/values/?id=" + endpoint.id + "&value=" + str(endpoint.value))
            elif endpoint.location is not None and endpoint.name is not None:
                conn.request("GET", "/values/?location=" + endpoint.location + "&name=" + endpoint.name + "&value=" + str(endpoint.value))
            response = conn.getresponse()
            if response.reason == "OK":
                return json.loads(response.read())
        except:
            raise LagartoException("Unable to get response from HTTP server")

        return None


    def __init__(self, working_dir):
        '''
        Constructor
        
        @param working_dir: Working directory
        '''
        threading.Thread.__init__(self)
        LagartoProcess.__init__(self, working_dir)
        
        self.running = True
       
        # ZMQ PUSH socket
        self.sub_socket = None
        
        # Create ZeroMQ sockets
        self.context = zmq.Context()

        # ZMQ PUB socket
        self.sub_socket = None
        if self.config.broadcast is not None:
            self.sub_socket = self.context.socket(zmq.SUB)

            # Bind/connect ZMQ SUB socket
            try:
                # Try binding socket first
                if self.sub_socket.bind(self.config.broadcast) == -1:
                    raise LagartoException("Unable to bind zmq sub socket to " + self.config.broadcast)
                else:
                    self.sub_socket.setsockopt(zmq.SUBSCRIBE, "")
                    logging.info("ZMQ SUB socket binded to", self.config.broadcast)
            except zmq.ZMQError as ex:
                try:
                    # Now try connecting to the socket
                    if self.sub_socket.connect(self.config.broadcast) == -1:
                        raise LagartoException("Unable to connect zmq sub socket to " + self.config.broadcast)
                    else:
                        logging.info("ZMQ SUB socket connected to ", self.config.broadcast)
                except zmq.ZMQError as ex:
                    raise LagartoException("Unable to establish connection with zmq sub socket")


        # List of HTTP servers
        self.http_servers = {}


class LagartoBroker(LagartoClient):
    """
    Lagarto broker class
    """

    def _process_event(self, event):
        """
        Process lagarto event
        
        @param event: event packet to be processed
        """
        # Publish event downstream
        self.pub_socket.send(event)
        
        # Run the rest of the client tasks
        LagartoClient._process_event(self, event)
                      

    def stop(self):
        """
        Stop lagarto server
        """
        # Close ZeroMQ socket
        self.pub_socket.setsockopt(zmq.LINGER, 0)
        self.pub_socket.close()
        
        # Close Lagarto client
        LagartoClient.stop(self)
        
        
    def __init__(self, working_dir):
        '''
        Constructor
        
        @param working_dir: Working directory
        '''
        LagartoClient.__init__(self, working_dir)

        addr = self.config.broadcast.split(':')

        if len(addr) < 3:
            raise LagartoException("Incorrect broadcast address:port, " + self.config.broadcast)
        
        port = int(addr[2]) + 1
        
        pub_address = addr[0] + ':' + addr[1] + ':' + str(port)
        
        # ZMQ PUB socket
        self.pub_socket = None

        # PUB socket between broker and clients
        try:
            self.pub_socket = self.context.socket(zmq.PUB)
            if self.pub_socket.bind(pub_address) == -1:
                raise LagartoException("Unable to bind ZMQ PUB socket to " + pub_address)
            else:
                logging.info("ZMQ PUB socket binded to", pub_address)
        except zmq.ZMQError as ex:
            raise LagartoException("Unable to bind ZMQ PUB socket to " + pub_address + ": " + str(ex))
