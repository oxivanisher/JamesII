
import sys
from datetime import timedelta

import commands
from james.plugin import *

class SystemPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(SystemPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('ip', 'show the ip of this node', self.get_ip)
        self.commands.create_subcommand('proximity', 'show proximity location and state', self.show_proximity)
        self.commands.create_subcommand('plugins', 'show the running plugins on this node', self.show_plugins)
        if os.path.isfile('/usr/bin/git'):
            self.commands.create_subcommand('version', 'shows the git checkout HEAD', self.cmd_version)
        if self.core.master:
            self.commands.create_subcommand('msg', 'sends a message', self.cmd_message)
            self.commands.create_subcommand('quit', 'quit the system', self.cmd_quit)
            self.commands.create_subcommand('ping', 'ping all available nodes over rabbitmq', self.cmd_ping)

    def get_ip(self, args):
        return commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | " +
                         "awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'")

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
    'help' : 'system commands',
    'command' : 'sys',
    'mode' : PluginMode.AUTOLOAD,
    'class' : SystemPlugin
}
