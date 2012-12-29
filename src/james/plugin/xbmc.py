
import sys

from james.plugin import *

class XbmcPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(XbmcPlugin, self).__init__(core, descriptor)

    def terminate(self):
        pass

    def cmd_xbmc(self, args):
        return 'args: ' + ' '.join(args)


descriptor = {
    'name' : 'xbmc',
    'help' : 'Xbmc test module',
    'command' : 'xbmc',
    'mode' : PluginMode.MANAGED,
    'class' : XbmcPlugin
}

