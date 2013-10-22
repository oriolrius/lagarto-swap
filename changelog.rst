===========================================
Oriol Rius and team changes on Lagarto SWAP
===========================================

Oct 22, 2013 - release #1
-------------------------

*Features:*

* log messages are sent to syslog no to stdout by default, you can force stdout messages using command line parameter '--stdout'
* log level can be setted using command line parameter '--level=LOG_ELVEL', example: --level=DEBUG
* location functionality, working using a XML tag in network.xml, example: <location>greenhouse01</location>
* you can disable HTTP commands, using XML tag in lagarto.xml: http_disable_set_value, example: <http_disable_set_value>True</http_disable_set_value>
* "inp" endpoints are published in a MQTT server with topic: /location/measures/id, example: /greenhouse01/measures/2.11.0
* "out" endpoints values are read from MQTT server with topic: /location/actions/id, example: /greenhouse01/actions/2.12.0
* plugin system to manipulate endpoint messages coming or going to MQTT network
* MQTT parameters in lagarto.xml::

                <mqtt>
                    <host>localhost</host>
                    <port>1883</port>
                    <client_id>test</client_id>
                    <plugin>timestamp_plugin.timestamp.TimestampPlugin</plugin>
                    <plugin>timestamp_plugin.roundtime.RoundTime</plugin>
                </mqtt>

* Plugin: TimeStamp, converts time stamp format and supports TTL. If TTL is ended the messages i dropped.
* Plugin: RoundTime, converts time stamp values to rounded values, example: if you have a reading at 12:11:03 it can be rounded to 12:11:00 or to 12:00:00 or 12:15:00 it depends on how you want to round the time stamp

*Solved:*

* now you can stop server using a TERM or KILL (control-c) signal without hang up problems
* if modem can not be resetted starting lagarto SWAP the process dies and returns to shell

