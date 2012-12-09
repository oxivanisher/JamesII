
import subprocess
import sys
from time import localtime, strftime

from james.plugin import *

class MonitorPlugin(Plugin):

    def __init__(self, core):
        super(MonitorPlugin, self).__init__(core, MonitorPlugin.name)

    def terminate(self):
        pass

    def process_message(self, message):
        self.format_output(("%s@%s" % (message.sender_name, message.sender_host)),
                            "New Message",
                            ("[%s] %s; %s" % (message.level, message.header, message.body)))

    def process_proximity_event(self, newstatus):
        self.format_output(("%s@%s" % (newstatus['plugin'], newstatus['host'])),
                            "Proximity Event",
                            ("%s: %s" % (newstatus['location'], newstatus['status'][newstatus['location']])))

    def process_command_request_event(self, command):
        self.format_output(("%s@%s" % (command['plugin'], command['host'])),
                            "Command Request",
                            ("%s: %s" % (command['uuid'], command['body'])))

    def process_command_response_event(self, command):
        self.format_output(("%s@%s" % (command['plugin'], command['host'])),
                            "Command Response",
                            ("%s: %s" % (command['uuid'], command['body'])))

    def process_discovery_event(self, msg):
        self.format_output(("%s" % (msg[1])),
                            "Discovery Event",
                            ("%s" % (msg[0])))

    def format_output(self, who, what, payload):
        nicetime = strftime("%H:%M:%S", localtime())
        print("%8s %-20s %-20s %s" % (nicetime, who, what, payload))

descriptor = {
    'name' : 'monitor',
    'mode' : PluginMode.MANAGED,
    'class' : MonitorPlugin
}
