
import subprocess
import sys
from time import localtime, strftime

from james.plugin import *

class LoggerPlugin(Plugin):

    def __init__(self, core):
        super(LoggerPlugin, self).__init__(core, LoggerPlugin.name)

        self.core = core
        self.unmuted = self.core.proximity_status.get_status_here()

        self.create_command('logger_status', self.cmd_logger_status, 'say something')
        self.archived = {}

    def terminate(self):
        pass

    def cmd_logger_status(self, args):
        pass

    def process_message(self, message):
        print("process message event: %s" % (message))
        pass
        # if message.level > 0:
        #     if self.unmuted:
        #         print("Espeak is speaking a message from %s@%s:\n%s:%s" % (message.sender_name,
        #                                                                 message.sender_host,
        #                                                                 message.header,
        #                                                                 message.body))
        #         self.speak(message.header)
        #     else:
        #         self.archived[message.timestamp] = message.header

    def process_proximity_event(self, newstatus):
        print("process proximity event: %s - %s" % (self.core.location, newstatus)) #ok
        pass
        # self.unmuted = newstatus
        # if newstatus:
        #     self.greet_homecomer()

    def process_command_request_event(self, command):
        print("process command request event: %s" % (command))
        pass

    def process_command_response_event(self, command):
        print("process command response event: %s" % (command))
        pass

    def process_discovery_event(self, msg):
        print("process discovery event: %s" % (msg)) #ok
        pass

    def process_config_event(self, config):
        print("process config event: %s" % (config)) #ok
        pass

    def format_output(self, ):
        pass


descriptor = {
    'name' : 'logger',
    'mode' : PluginMode.MANAGED,
    'class' : LoggerPlugin
}
