
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
        pass
        # self.unmuted = newstatus
        # if newstatus:
        #     self.greet_homecomer()

    def process_command_event(self, command):
        pass

    def process_discovery_event(self, msg):
        pass


    # command methods
    def handle_request(self, uuid, name, body):
        pass

    def handle_response(self, uuid, name, body):
        pass


descriptor = {
    'name' : 'logger',
    'mode' : PluginMode.MANAGED,
    'class' : LoggerPlugin
}
