
import sys
from datetime import timedelta

import commands
from james.plugin import *

class SystemPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(SystemPlugin, self).__init__(core, descriptor)

        self.crash_detection_file = os.path.join(os.getcwd(), ".james_crashed")

        self.commands.create_subcommand('ip', 'Show the ip of this node', self.get_ip)
        if self.core.master:
            self.commands.create_subcommand('msg', 'Sends a message (head[;body])', self.cmd_message)
            self.commands.create_subcommand('ping', 'Ping all available nodes over rabbitmq', self.cmd_ping)
        self.commands.create_subcommand('plugins', 'Show the running plugins on this node', self.show_plugins)
        self.commands.create_subcommand('proximity', 'Show proximity location and state', self.show_proximity)
        if self.core.master:
            self.commands.create_subcommand('quit', 'Quits the system JamesII. Yes, every node will shut down!', self.cmd_quit)
        if os.path.isfile('/usr/bin/git'):
            self.commands.create_subcommand('version', 'Shows the git checkout HEAD', self.cmd_version)

    def get_ip(self, args):
        return commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | " +
                         "awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'")

    def start(self):
        try:
            file = open(self.crash_detection_file, 'r')
            timestamp = int(file.read())
            file.close()
            if self.core.config['core']['debug']:
                print("Checking for crash restart in %s" % (self.crash_detection_file))
            os.remove(self.crash_detection_file)
            self.send_broadcast(['JamesII started after crash %s' % (self.core.utils.get_nice_age(timestamp))])

            message = self.core.new_message(self.name)
            message.level = 2
            message.header = ("James crash recovery detected on %s %s" % (self.core.hostname, self.core.utils.get_nice_age(timestamp)))
            message.send()

        except IOError:
            pass
        pass

    def show_proximity(self, args):
        return ("%-10s %-10s %s" % (self.core.hostname,
                                  self.core.proximity_status.get_status_here(),
                                  self.core.location))

    def show_plugins(self, args):
        plugin_names = []
        for p in self.core.plugins:
            plugin_names.append(p.name)
        return([', '.join(plugin_names)])


    def cmd_version(self, args):
        version_pipe = os.popen('/usr/bin/git log -n 1 --pretty="format:%h %ci"')
        version = version_pipe.read().strip()
        version_pipe.close()
        return version

    def cmd_message(self, args):
        message_string = ' '.join(args)
        message_list = message_string.split(';')

        message = self.core.new_message("cli_message")
        message.level = 1
        try:
            message.body = message_list[1].strip()
        except IndexError:
            message.body = None

        try:
            message.header = message_list[0].strip()
            message.send()
            return ("Message header: %s; body: %s" % (message.header, message.body))
        except Exception as e:
            return ("Message could not me sent (%s)" % (e))

    def cmd_quit(self, args):
        message = self.core.new_message(self.name)
        message.header = ("JamesII shutting down (%s@%s)" % (self.name, self.core.hostname))
        message.level = 2
        message.send()

        self.core.discovery_channel.send(['shutdown', self.core.hostname, self.uuid])

    def cmd_ping(self, args):
        self.core.ping_nodes()

descriptor = {
    'name' : 'system',
    'help' : 'JamesII system commands',
    'command' : 'sys',
    'mode' : PluginMode.AUTOLOAD,
    'class' : SystemPlugin
}
