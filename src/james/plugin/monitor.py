import os
from time import localtime, strftime

from james.plugin import *


class MonitorPlugin(Plugin):

    def __init__(self, core, descriptor):
        super().__init__(core, descriptor)

        self.message_cache = []
        self.max_message_cache = 50
        self.file_cache = []
        self.max_file_cache = 20
        self.file_cache_name = os.path.join(os.path.expanduser("~"), ".james_monitor_log")

        self.commands.create_subcommand('show', ('Shows the last %s messages' % self.max_message_cache),
                                        self.cmd_showlog)
        self.commands.create_subcommand('save', 'Saves all cached messages to the log file.', self.cmd_save_to_logfile)

    def terminate(self):
        self.file_cache.append(f"{strftime('%Y-%m-%d %H:%M:%S', localtime())} JamesII is shutting down.")
        self.save_log_to_disk()

    def start(self):
        self.file_cache.append(f"{strftime('%H:%M:%S %d.%m.%Y', localtime())} JamesII started with (UUID {self.core.uuid})")
        self.save_log_to_disk()

    def cmd_showlog(self, args):
        ret = []
        for message in self.message_cache:
            ret.append(message)
        return ret

    def cmd_save_to_logfile(self, args):
        return self.save_log_to_disk()

    def format_output(self, message):
        return f"{strftime('%H:%M:%S', message['timestamp']):8} {message['who']:<20} {message['what']:<20} {message['payload']}"

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
            self.logger.debug(f"Saving monitor log to {self.file_cache_name}")
            self.file_cache = []
            return ["Monitor logfile saved"]
        except IOError:
            sys_msg = "Could not save monitor log to file!"
            self.logger.warning(sys_msg)
            self.system_message_add(sys_msg)

    def process_message(self, message):
        self.process_event(f"{message.sender_name}@{message.sender_host}",
                           "New Message",
                           f"L{message.level} {message.header}; {message.body}")

    def process_presence_event(self, presence_before, presence_now):
        self.process_event(f"{presence_now['plugin']}@{presence_now['host']}", "Presence Event",
                           f"{presence_now['location']}: {', '.join(presence_now['users'])}")

    def process_command_request_event(self, command):
        self.process_event(f"{command['plugin']}@{command['host']}",
                           "Command Request",
                           f"{' '.join(command['body'])} ({command['uuid']})")

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

        self.process_event(f"{command['plugin']}@{command['host']}",
                           "Command Response",
                           f"Lines: {lines}; Bytes: {bytes_count} ({command['uuid']})")

    def process_discovery_event(self, msg):
        events = ['hello', 'byebye', 'shutdown']  # 'ping', 'pong'
        if msg[0] in events:
            self.process_event(f"core@{msg[1]}",
                               "Discovery Event",
                               f"{msg[0]} ({msg[2]})")

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
