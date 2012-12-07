
import sys

from james.plugin import *

class XbmcPlugin(Plugin):

    def __init__(self, core):
        super(XbmcPlugin, self).__init__(core, XbmcPlugin.name)

        self.create_command('xbmc', self.cmd_xbmc, 'xbmc test module')

    def terminate(self):
        pass

    def cmd_xbmc(self, args):
        return 'args: ' + ' '.join(args)


descriptor = {
    'name' : 'xbmc',
    'mode' : PluginMode.MANAGED,
    'class' : XbmcPlugin
}

