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
__date__  ="Oct 17, 2013"
#########################################################################

import logging
import copy
import sys
import traceback

class MqttPluginDropMessage(Exception):
    """
    Plugin can use this Exception to avoid
    push or pull one message and drop it
    """
    def __init__(self, msg):
        self._msg = msg
        Exception.__init__(self)

    def __str__(self):
        return self._msg



class MqttPluginInterface:
    """
    Plugin interface to get and handle messages
    incoming and outoing from Mqtt network

    MqttPluginInterface has to be Thread safe between 
    incoming or outgoing functions.
    """
    name = "Name of Plugin"
    author = "Author of Plugin"

    def incoming(self, message):
        """
        Override this function to get all messages
        are comming into Lagarto from Mqtt network.

        @param message dict
        @return dict
        """
        return message

    def outgoing(self, message):
        """
        Override this function to get all messages
        are going out to Mqtt network from Lagarto.

        @param message dict
        @return dict
        """
        return message


class MqttPluginHandleException(Exception):
    def __init__(self, msg):
        self._msg = msg
        Exception.__init__(self)

    def __str__(self):
        return self._msg


class MqttPluginHandle:
    """
    Load and run all plugins registered at system
    """

    PLUGINS = []  # save class plugins at Class object

    def incoming(self, message):
        """
        Run all plugins for one incoming message
        """
        src_msg = copy.copy(message)
        return self._run_plugins(src_msg, type_ = "incoming")

    def outgoing(self, message):
        """
        Run all plugins for one outgoing message
        """
        src_msg = copy.copy(message)
        return self._run_plugins(src_msg, type_ = "outgoing")


    def _run_plugins(self, message, type_ = "incoming"):
        for plugin in MqttPluginHandle.PLUGINS:
            try:
                f = getattr(plugin, type_)
                message = f(message)
            except MqttPluginDropMessage, e:
                logging.warning("Plugin drop message recived from %s" %\
                              plugin.name)
                raise e
            except Exception, e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback)
                logging.debug("Plugin exception: message %s" % message)
                logging.warning("Plugin exception: %s" % plugin.name)
                logging.warning("Plugin exception: incoming function")
                logging.warning("Plugin exception: %s" % str(e))
            
        return message

    @classmethod
    def load_plugin(cls, str_module):
        """
        Try to load and register str_module. Code inspired from django

        @param str_module a dotted path with Plugin class at end of it
               path.modulename.ClassPlguin
        """
        try:
            module_path, class_name = str_module.rsplit('.', 1)
        except ValueError:
            raise MqttPluginHandleException("%s doesn't look like a module path" %
                str_module)
        try:
            __import__(module_path)
            module = sys.modules[module_path]
        except ImportError as e:
            raise MqttPluginHandleException('Error importing module %s: "%s"' % (
                module_path, e))
        try:
            attr = getattr(module, class_name)
        except AttributeError:
             raise MqttPluginHandleException('Module "%s" does not define a "%s" attribute/class' % (
                module_path, class_name))

        MqttPluginHandle.PLUGINS.append(attr())

