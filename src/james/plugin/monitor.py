
import subprocess
import sys
from time import localtime, strftime

from james.plugin import *

class MonitorPlugin(Plugin):

    def __init__(self, core):
        super(MonitorPlugin, self).__init__(core, MonitorPlugin.name)

        self.create_command('log', self.cmd_showlog, 'show the log of the monitor')

        self.archive = []
        self.max_archived_messages = 1000

    def terminate(self):
        pass

    def process_message(self, message):
        self.process_event(("%s@%s" % (message.sender_name, message.sender_host)),
                            "New Message",
                            ("L%s %s; %s" % (message.level, message.header, message.body)))

    def process_proximity_event(self, newstatus):
        self.process_event(("%s@%s" % (newstatus['plugin'], newstatus['host'])),
                            "Proximity Event",
                            ("%s: %s" % (newstatus['location'], newstatus['status'][newstatus['location']])))

    def process_command_request_event(self, command):
        self.process_event(("%s@%s" % (command['plugin'], command['host'])),
                            "Command Request",
                            ("%s (%s)" % (command['body'], command['uuid'])))

    def process_command_response_event(self, command):
        self.process_event(("%s@%s" % (command['plugin'], command['host'])),
                            "Command Response",
                            ("%s (%s)" % (command['body'], command['uuid'])))

    def process_discovery_event(self, msg):
        self.process_event(("%s" % (msg[1])),
                            "Discovery Event",
                            ("%s (%s)" % (msg[0], msg[2])))

    def process_event(self, who, what, payload):
        message = {}
        message['who'] = who
        message['what'] = what
        message['payload'] = payload
        message['timestamp'] = localtime()

        self.log_message(message)
        print self.format_output(message)

    def format_output(self, message):
        return ("%8s %-20s %-20s %s" % (strftime("%H:%M:%S", message['timestamp']),
                                      message['who'],
                                      message['what'],
                                      message['payload']))

    def log_message(self, message):
        self.archive.insert(0, message)
        while len(self.archive) > self.max_archived_messages:
            self.archive.pop()

    def cmd_showlog(self, args):
        ret = []
        for message in self.archive:
            ret.append(self.format_output(message))
        return ret

descriptor = {
    'name' : 'monitor',
    'mode' : PluginMode.MANAGED,
    'class' : MonitorPlugin
}
