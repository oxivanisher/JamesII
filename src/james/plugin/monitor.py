import os
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

        self.commands.create_subcommand('show', ('Shows the last %s messages' % self.max_message_cache),
                                        self.cmd_showlog)
        self.commands.create_subcommand('save', 'Saves all cached messages to the log file.', self.cmd_save_to_logfile)

    def terminate(self):
        self.file_cache.append("%s JamesII is shutting down." % (strftime("%Y-%m-%d %H:%M:%S", localtime())))
        self.save_log_to_disk()

    def start(self):
        self.file_cache.append("%s JamesII started with (UUID %s)" % (strftime("%H:%M:%S %d.%m.%Y", localtime()),
                                                                      self.core.uuid))
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
            file.write('\n'.join(self.utils.list_unicode_cleanup(self.file_cache)) + '\n')
            file.close()
            self.logger.debug("Saving monitor log to %s" % self.file_cache_name)
            self.file_cache = []
            return ["Monitor logfile saved"]
        except IOError:
            self.logger.warning("Could not save monitor log to file!")

    def process_message(self, message):
        self.process_event(("%s@%s" % (message.sender_name, message.sender_host)),
                           "New Message",
                           ("L%s %s; %s" % (message.level, message.header, message.body)))

    def process_presence_event(self, presence_before, presence_now):
        self.process_event(("%s@%s" % (presence_now['plugin'], presence_now['host'])), "Presence Event",
                           ("%s: %s" % (presence_now['location'], ', '.join(presence_now['users']))))

    def process_command_request_event(self, command):
        self.process_event(("%s@%s" % (command['plugin'], command['host'])),
                           "Command Request",
                           ("%s (%s)" % (' '.join(command['body']), command['uuid'])))

    def process_command_response_event(self, command):
        bytes_count = 0
        lines = 0
        try:
            for line in command['body']:
                bytes_count += len(line)
                lines = len(command['body'])
        except TypeError:
            bytes_count = 1
            lines = 1
            pass

        self.process_event(("%s@%s" % (command['plugin'], command['host'])),
                           "Command Response",
                           ("Lines: %s; Bytes: %s (%s)" % (lines, bytes_count, command['uuid'])))

    def process_discovery_event(self, msg):
        events = ['hello', 'byebye', 'shutdown']  # 'ping', 'pong'
        if msg[0] in events:
            self.process_event(("core@%s" % (msg[1])),
                               "Discovery Event",
                               ("%s (%s)" % (msg[0], msg[2])))

    def process_event(self, who, what, payload):
        message = {'who': who, 'what': what, 'payload': payload, 'timestamp': localtime()}

        formatted_output = self.format_output(message)
        print(self.process_log_message(formatted_output))


descriptor = {
    'name': 'monitor',
    'help_text': 'Console monitor plugin',
    'command': 'mon',
    'mode': PluginMode.MANAGED,
    'class': MonitorPlugin,
    'detailsNames': {}
}
