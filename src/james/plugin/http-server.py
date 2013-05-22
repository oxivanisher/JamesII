# http://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world

import time

from james.plugin import *

# http://stackoverflow.com/questions/713847/recommendations-of-python-rest-web-services-framework
# http://docs.python.org/2/library/socketserver.html
# http://www.linuxjournal.com/content/tech-tip-really-simple-http-server-python

# http://stackoverflow.com/questions/14444913/web-py-specify-address-and-port

class HttpServerPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(HttpServerPlugin, self).__init__(core, descriptor)

        self.externalSystemStatus = {}
        self.hostnames = {}

        self.command_responses = []
        self.broadcast_command_responses = []

        self.commands.create_subcommand('test', 'Print a test message to console', self.cmd_print_test)
        self.commands.create_subcommand('show', 'Show current status info', self.cmd_print_status)

        self.node_update_loop()

    # external commands (must be threadsafe!)
    def ext_request_all_nodes_details(self):
        self.core.add_timeout(0, self.send_data_request, 'status')

    def ext_send_command(self, command):
        self.core.add_timeout(0, self.send_command, command)
        self.logger.debug('Running command (%s) from %s' % (' '.join('command'), host))

    # internal commands
    def node_update_loop(self):
        self.ext_request_all_nodes_details()
        self.core.add_timeout(20, self.node_update_loop)

    def process_command_response(self, args, host, plugin):
        self.command_responses.append((time.time(),
                                       self.utils.convert_from_unicode(args),
                                       self.utils.convert_from_unicode(host),
                                       self.utils.convert_from_unicode(plugin) ))
        self.logger.debug('Saved command response from %s' % host)

    def process_broadcast_command_response(self, args, host, plugin):
        self.broadcast_command_responses.append((time.time(),
                                                 self.utils.convert_from_unicode(args),
                                                 self.utils.convert_from_unicode(host),
                                                 self.utils.convert_from_unicode(plugin) ))
        self.logger.debug('Saved broadcast command response from %s' % host)

    def process_data_response(self, uuid, name, body, host, plugin):
        if name == 'status':
            uuid = self.utils.convert_from_unicode(uuid)
            plugin = self.utils.convert_from_unicode(plugin)

            self.hostnames[uuid] = self.utils.convert_from_unicode(host)

            try:
                self.externalSystemStatus[uuid]
            except KeyError:
                self.externalSystemStatus[uuid] = {}

            try:
                self.externalSystemStatus[uuid][plugin]
            except KeyError:
                self.externalSystemStatus[uuid][plugin] = {}

            self.externalSystemStatus[uuid][plugin] = { 'status'   : self.utils.convert_from_unicode(body),
                                                        'timestamp': time.time() }

    # internal command methods
    def cmd_print_test(self, args):
        print "console test"

    def cmd_print_status(self, args):
        print self.externalSystemStatus

descriptor = {
    'name' : 'http-server',
    'help' : 'Webfrontend for JamesII',
    'command' : 'http',
    'mode' : PluginMode.MANUAL,
    'class' : HttpServerPlugin,
    'detailsNames' : {}
}
