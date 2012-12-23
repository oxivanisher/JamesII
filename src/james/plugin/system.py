
import sys
from datetime import timedelta

import commands
from james.plugin import *

class SystemPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(SystemPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('ip', 'show the ip of this node', self.get_ip)
        if os.path.isfile('/usr/bin/git'):
            self.commands.create_subcommand('version', 'shows the git checkout HEAD', self.cmd_version)
        if self.core.master:
            #FIXME not really me ... but my commands wont be shown in cli beacuse the cli probably overwrites the commands with his won :()
            self.commands.create_subcommand('quit', 'quit the system', self.cmd_quit)
            self.commands.create_subcommand('ping', 'ping all available nodes over rabbitmq', self.cmd_ping)
            self.commands.create_subcommand('at', 'execute command at given time', self.cmd_at)
            self.commands.create_subcommand('in', 'execute command in given time', self.cmd_in)


    def cmd_quit(self, args):
        message = self.core.new_message(self.name)
        message.header = ("JamesII shutting down (%s@%s)" % (self.name, self.core.hostname))
        message.level = 2
        message.send()

        self.core.discovery_channel.send(['shutdown', self.core.hostname, self.uuid])

    def cmd_version(self, args):
        version_pipe = os.popen('/usr/bin/git log -n 1 --pretty="format:%h %ci"')
        version = version_pipe.read().strip()
        version_pipe.close()
        return version

    def get_ip(self, args):
        return commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | " +
                         "awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'")

    def cmd_ping(self, args):
        self.core.ping_nodes()

    #FIXME: please make me
    def cmd_in(self, args):
        pass

    def cmd_at(self, args):
        pass

descriptor = {
    'name' : 'system',
    'help' : 'system commands',
    'command' : 'sys',
    'mode' : PluginMode.AUTOLOAD,
    'class' : SystemPlugin
}
