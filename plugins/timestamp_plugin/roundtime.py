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


def DoRoundTime(dt=None, roundTo=60):
   """Round a datetime object to any time laps in seconds
   dt : datetime.datetime object, default now.
   roundTo : Closest number of seconds to round to, default 1 minute.
   Author: Thierry Husson 2012 - Use it as you want but don't blame me.
   """
   if dt == None : dt = datetime.datetime.now()
   seconds = (dt - dt.min).seconds
   # // is a floor division, not a comment on following line:
   rounding = (seconds+roundTo/2) // roundTo * roundTo
   return dt + timedelta(0,rounding-seconds,-dt.microsecond)


class RoundTime(MqttPluginInterface):
    name = "Round Time plugin"
    author = ""

    FORMAT = "%Y-%m-%dT%H:%M:%S"

    def incoming(self, message):
        """
        Messages comming from Mqtt topic
        """
        return message

        
    def outgoing(self, message):
        """
        Messages going to Mqtt topic
        """
        
        date = datetime.strptime(message["timestamp"], self.FORMAT)
	date = DoRoundTime(date, roundTo=1*60)
	message["timestamp"] = date.strftime(self.FORMAT)

        return message
       
