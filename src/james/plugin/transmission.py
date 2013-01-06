
import transmissionrpc

from james.plugin import *

# https://bitbucket.org/blueluna/transmissionrpc/wiki/Home

class TransmissionPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(TransmissionPlugin, self).__init__(core, descriptor)

        connected = False
        try:
            self.tr_conn = transmissionrpc.Client(address=self.core.config['transmission']['nodes'][self.core.hostname]['host'])
            connected = True
        except Exception as e:
            print("Unable to connect to transmission: %s" % e)
            pass

        if connected:
            self.commands.create_subcommand('list', 'List current torrents', self.cmd_list)

    def terminate(self):
        pass

    def cmd_list(self, args):
        return self.tr_conn.list()
        # return 'args: ' + ' '.join(args)

    def cmd_test(self, args):
        # github_url = self.core."https://api.github.com/user/repos"
        # data = json.dumps({'name':'test', 'description':'some test repo'}) 
        # r = requests.post(github_url, data, auth=('user', '*****'))
        # print r.json
        pass


descriptor = {
    'name' : 'transmission',
    'help' : 'Transmission control plugin',
    'command' : 'tr',
    'mode' : PluginMode.MANAGED,
    'class' : TransmissionPlugin
}

