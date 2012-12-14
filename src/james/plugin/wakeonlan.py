
import sys

from james.plugin import *

class WakeOnLanPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(WakeOnLanPlugin, self).__init__(core, descriptor)

        self.core = core

        self.commands.create_subcommand('list', 'lists available wol target hosts', self.wol_list)
        self.commands.create_subcommand('wake', 'wakes up a given host', self.wol_wake)

    def wol_list(self, args):
        print("yay!")
        return ', '.join(self.core.config['wakeonlan']['targets'].keys())

    def wol_wake(self, args):
        host = None
        try:
            host = self.core.config['wakeonlan']['targets'][args[0]]
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
    'help' : 'wake on lan plugin',
    'command' : 'wol',
    'mode' : PluginMode.MANAGED,
    'class' : WakeOnLanPlugin
}

