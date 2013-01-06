
import jsonrpclib

from james.plugin import *


# http://forum.xbmc.org/showthread.php?tid=111772
# https://github.com/joshmarshall/jsonrpclib/

class XbmcPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(XbmcPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('update', 'Initiates a Database update', self.cmd_update)

        user_string = ""
        if self.core.config['xbmc']['nodes'][self.core.hostname]['username']:
            user_string = self.core.config['xbmc']['nodes'][self.core.hostname]['username']
        if self.core.config['xbmc']['nodes'][self.core.hostname]['password']:
            user_string = user_string + ":" + self.core.config['xbmc']['nodes'][self.core.hostname]['password']
        if user_string:
            user_string = user_string + "@"
        server_string = "%s:%s" % (self.core.config['xbmc']['nodes'][self.core.hostname]['host'],
                                   self.core.config['xbmc']['nodes'][self.core.hostname]['port'])
        connection_string = "http://%s%s/jsonrpc" % (user_string, server_string)
        self.xbmc_conn = jsonrpclib.Server(connection_string)

    def cmd_update(self, args):
        self.xbmc_conn.VideoLibrary.Scan()
        return 'args: ' + ' '.join(args)

descriptor = {
    'name' : 'xbmc',
    'help' : 'Xbmc test module',
    'command' : 'xbmc',
    'mode' : PluginMode.MANAGED,
    'class' : XbmcPlugin
}

