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
__date__ ="Oct, 17 2013"
#########################################################################

from lagartomqtt.plugin import MqttPluginHandle, MqttPluginHandleException

import logging

class MqttConfig(object):
    """
    Store Mqtt config atributes
    """
    def __init__(self, xml_parser):
        """
        Read mqtt configuration, getting info about
        host, port and client-id
        """
        tags = [("host", None),
                ("port", int),
                ("client_id", None)]

        for tag in tags:
            xml_tag = xml_parser.find(tag[0])
            if xml_tag is not None:
                f = tag[1] or (lambda x:x)
                setattr(self, tag[0], f(xml_tag.text))
            else:
                raise Exception("Mqtt param %s nout found,",\
                                " disable mqtt or set it" %  tag[0]) 

        # get all plugin tags
        self._plugins = []
        for plugin_tag in xml_parser.findall("plugin"):
            try:
                MqttPluginHandle.load_plugin(plugin_tag.text)
            except MqttPluginHandleException, e:
                logging.warning("Load Plugin rises error, disabled")
                logging.warning(str(e))
            finally:
                self._plugins.append(plugin_tag.text)  # only save config

    def save(self, fd, identation_level):
        """
        Save current configuration to file descriptor
        """
        f.write("\t" * identatino_level)
        f.write("<mqtt>\n");
        f.write("\t" * (identation_level + 1), "<host>", self.host, "</host>\n")
        f.write("\t" * (identation_level + 1), "<port>", self.port, "</port>\n")
        f.write("\t" * (identation_level + 1), "<client-id>", self.client_id, "</client-id>\n")
        for plugin in self._plugins:
            f.write("\t" * (identation_level + 1), "<plugin>", plugin, "</plugin>\n")
        f.write("\t" * identatino_level)
        f.write("</mqtt>\n");
 


