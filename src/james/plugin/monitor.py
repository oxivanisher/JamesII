
import subprocess
import sys
from time import localtime, strftime

from james.plugin import *

class MonitorPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(MonitorPlugin, self).__init__(core, descriptor)

        self.message_cache = []
        self.max_message_cache = 50
        self.file_cache = []
        self.max_file_cache = 20
        self.file_cache_name = os.path.join(os.path.expanduser("~"), ".james_monitor_log")

        self.commands.create_subcommand('show', ('Shows the last %s messages' % self.max_message_cache), self.cmd_showlog)
        self.commands.create_subcommand('save', ('Saves all cached messages to the log file.'), self.cmd_save_to_logfile)

    def terminate(self):
        self.file_cache.append("%s JamesII is shuttind down." % (strftime("%Y-%m-%d %H:%M:%S", localtime())))
        self.save_log_to_disk()

    def start(self):
        self.file_cache.append("%s JamesII started with (UUID %s)" % (strftime("%H:%M:%S %d.%m.%Y", localtime()), self.core.uuid))
        self.save_log_to_disk()

    def cmd_showlog(self, args):
        ret = []
        for message in self.message_cache:
            ret.append(message)
        return ret

    def cmd_save_to_logfile(self, args):
        return self.save_log_to_disk()

    def format_output(self, message):
        return ("%8s %-20s %-20s %s" % (strftime("%H:%M:%S", message['timestamp']),
                                        message['who'],
                                        message['what'],
                                        message['payload']))

    def process_log_message(self, message):
        self.message_cache.insert(0, message)
        while len(self.message_cache) > self.max_message_cache:
            self.message_cache.pop()

        self.file_cache.append(message)
        if len(self.file_cache) >= self.max_file_cache:
            self.save_log_to_disk()

        return message

    def save_log_to_disk(self):
        try:
            file = open(self.file_cache_name, 'a')
            file.write('\n'.join(self.core.utils.list_unicode_cleanup(self.file_cache)) + '\n')
            file.close()
            self.logger.debug("Saving monitor log to %s" % (self.file_cache_name))
            self.file_cache = []
            return ["Monitor logfile saved"]
        except IOError:
            self.logger.warning("Could not save monitor log to file!")

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
                            ("%s (%s)" % (' '.join(command['body']), command['uuid'])))

    def process_command_response_event(self, command):
        bytes = 0
        try:
            for line in command['body']:
                bytes += len(line)
                lines = len(command['body'])
        except TypeError:
            bytes = 1
            lines = 1
            pass

        self.process_event(("%s@%s" % (command['plugin'], command['host'])),
                            "Command Response",
                            ("Lines: %s; Bytes: %s (%s)" % (lines, bytes, command['uuid'])))

    def process_discovery_event(self, msg):
        events = ['hello', 'byebye', 'shutdown'] #'ping', 'pong'
        if msg[0] in events:
           self.process_event(("core@%s" % (msg[1])),
                               "Discovery Event",
                               ("%s (%s)" % (msg[0], msg[2])))

    def process_event(self, who, what, payload):
        message = {}
        message['who'] = who
        message['what'] = what
        message['payload'] = payload
        message['timestamp'] = localtime()

        formated_output = self.format_output(message)
        print self.process_log_message(formated_output)

descriptor = {
    'name' : 'monitor',
    'help' : 'Console monitor plugin',
    'command' : 'mon',
    'mode' : PluginMode.MANAGED,
    'class' : MonitorPlugin
}
