
import sys

from james.plugin import *

class WakeOnLanPlugin(Plugin):

    def __init__(self, core):
        super(WakeOnLanPlugin, self).__init__(core, WakeOnLanPlugin.name)

        self.core = core

        self.create_command('wol', self.cmd_wol, 'wake on lan')

    def cmd_wol(self, args):
        sub_commands = {'list' : self.wol_list,
                        'wake' : self.wol_wake}

        output = ("subcommands are: %s" % (', '.join(sub_commands.keys())))
        try:
            user_command = args[0]
        except Exception as e:
            return (output)
        for command in sub_commands.keys():
            if command == user_command:
                return sub_commands[command](args[1:])
        return (output)

    def wol_list(self, args):
        return ', '.join(self.core.config['wake_on_lan'].keys())

    def wol_wake(self, args):
        host = None
        try:
            host = self.core.config['wake_on_lan'][args[0]]
        except Exception as e:
            return "no valid hostname given"

        if host:
            self.core.utils.wake_on_lan(host)
            output = ("waking %s (%s)" % (args[0], host))
            
            message = self.core.new_message(self.name)
            message.header = "Wake on Lan"
            message.body = output
            message.send()

            return output

descriptor = {
    'name' : 'wakeonlan',
    'mode' : PluginMode.MANAGED,
    'class' : WakeOnLanPlugin
}

