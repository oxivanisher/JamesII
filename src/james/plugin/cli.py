
import threading
import sys
import yaml

from james.plugin import *

class ConsoleThread(threading.Thread):

    def __init__(self, plugin):
        super(ConsoleThread, self).__init__()
        self.plugin = plugin
        self.terminated = False

    def run(self):
        while (not self.terminated):
            try:
                sys.stdout.write('# ')
                line = sys.stdin.readline()
            except KeyboardInterrupt:
                self.plugin.core.terminate()
            line = line.strip()
            if (line == 'exit'):
                self.plugin.core.terminate()
            elif (line == 'dump_config'):
                print("Dumping config:")
                print(yaml.dump(self.plugin.core.config))
            elif (line == 'message'):
                print("Sending test message")
                message = self.plugin.core.new_message("cli_test")
                message.body = "Test Body"
                message.header = "Test Head"
                message.level = 1
                message.send()
            elif (line == 'prx'):
                print("proximity_status : %s" % (self.plugin.core.proximity_status.get_all_status()))
                print("self.location : %s" % (self.plugin.core.location))
            elif (line == 'prx_home'):
                self.plugin.core.proximity_status.set_status_here(True, 'cli')
            elif (line == 'prx_away'):
                self.plugin.core.proximity_status.set_status_here(False, 'cli')

            args = line.split(' ')
            self.plugin.send_command(args)

    def terminate(self):
        self.terminated = True


class CliPlugin(Plugin):

    def __init__(self, core):
        super(CliPlugin, self).__init__(core, CliPlugin.name)

        self.console_thread = ConsoleThread(self)

        sys.stdout.write('Interactive cli interface to james online. server: ')
        sys.stdout.write(self.core.brokerconfig['host'] + ':')
        sys.stdout.write('%s\n' % (self.core.brokerconfig['port']))
        sys.stdout.write('basic commands are help, message, dump_config and exit.' + '\n')

        self.console_thread.start()

    def terminate(self):
        self.console_thread.terminate()

    def process_command_response(self, args):
        print '\n'.join(args)

    def process_message(self, message):
        if message.sender_uuid != self.core.uuid:
            print("Recieved Message from '%s@%s'" % (message.sender_name, message.sender_host))
            print("Header: '%s'; Body: '%s'" % (message.header, message.body))      

    # proximity methods
    def process_proximity_event(self, newstatus):
        print("proximity event fired! '%s'" % (newstatus))



descriptor = {
    'name' : 'cli',
    'mode' : PluginMode.MANUAL,
    'class' : CliPlugin
}
