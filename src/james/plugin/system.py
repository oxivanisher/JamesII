
import sys
from datetime import timedelta

import commands
from james.plugin import *

class SystemPlugin(Plugin):

    def __init__(self, core):
        super(SystemPlugin, self).__init__(core, SystemPlugin.name)

        self.create_command('sys', self.cmd_sys, 'system commands')

    def cmd_sys(self, args):
        sub_commands = {'ip' : self.get_ip,
                        'quit' : self.cmd_quit,
                        'ping' : self.cmd_ping}
        if os.path.isfile('/usr/bin/git'):
            sub_commands['version'] = self.version
        output = ("subcommands are: %s" % (', '.join(sub_commands.keys())))
        try:
            user_command = args[0]
        except Exception as e:
            return (output)
        for command in sub_commands.keys():
            if command == user_command:
                return sub_commands[command](args[1:])
        return (output)

    def cmd_quit(self, args):
        message = self.core.new_message(self.name)
        message.header = ("JamesII shutting down (%s@%s)" % (self.name, self.core.hostname))
        message.leve = 2
        message.send()

        self.core.terminate()

    if os.path.isfile('/usr/bin/git'):
        def version(self, args):
            version_pipe = os.popen('/usr/bin/git log -n 1 --pretty="format:%h %ci"')
            version = version_pipe.read().strip()
            version_pipe.close()
            return version

    def get_ip(self, args):
        return commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | " +
                         "awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'")

    def cmd_ping(self, args):
        self.core.discovery_channel.send(['ping', self.core.hostname, self.core.uuid])

descriptor = {
    'name' : 'system',
    'mode' : PluginMode.AUTOLOAD,
    'class' : SystemPlugin
}
