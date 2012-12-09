
import sys

from james.plugin import *

class WakeOnLanPlugin(Plugin):

    def __init__(self, core):
        super(WakeOnLanPlugin, self).__init__(core, WakeOnLanPlugin.name)

        self.core = core

        self.create_command('wol', self.cmd_wol, 'wake on lan')

    def cmd_wol(self, args):
        sub_commands = "list, wake"

        try:
            sub_command = args[0]
        except Exception as e:
            return ("subcommands are: %s" % (sub_commands))

        if sub_command == "list":
            return self.wol_list(args[1:])
        elif sub_command == "wake":
            return self.wol_wake(args[1:])
        else:
            return ("invalid subcommand: %s" % (sub_command))

    def wol_list(self, args):
        return ', '.join(self.core.config['wake_on_lan'].keys())

    def wol_wake(self, args):
        host = None
        try:
            host = self.core.config['wake_on_lan'][args[0]]
        except Exception as e:
            return "No valid hostname given"

        if host:
            self.core.utils.wake_on_lan(host)
            output = ("Waking up %s (%s)" % (args[0], host))
            
            message = self.core.new_message(self.name)
            message.header = "Wake on lan"
            message.body = output
            message.send()

            return output

descriptor = {
    'name' : 'wakeonlan',
    'mode' : PluginMode.MANAGED,
    'class' : WakeOnLanPlugin
}

