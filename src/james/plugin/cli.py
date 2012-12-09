
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

        sys.stdout.write('Interactive cli interface to james online. server: ')
        sys.stdout.write(self.plugin.core.brokerconfig['host'] + ':')
        sys.stdout.write('%s\n' % (self.plugin.core.brokerconfig['port']))
        sys.stdout.write('basic commands are help, message, dump_config and exit.' + '\n')

        while (not self.terminated):
            try:
                #sys.stdout.write('# ')
                line = sys.stdin.readline()
            except KeyboardInterrupt:
                self.plugin.core.terminate()
            line = line.strip()
            if (line == 'exit'):
                self.plugin.core.terminate()
            elif (line == 'dump_config'):
                print("dumping config:")
                print(yaml.dump(self.plugin.core.config))
            elif (line == 'message'):
                print("sending test message")
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

            if len(line.rstrip()) > 0:
                args = line.split(' ')
                self.plugin.send_command(args)
            else:
                print("enter 'help' for a list of available commands.")

    def terminate(self):
        self.terminated = True


class CliPlugin(Plugin):

    def __init__(self, core):
        super(CliPlugin, self).__init__(core, CliPlugin.name)

        self.console_thread = None
        self.cmd_line_mode = len(sys.argv) > 1

    def start(self):
        if self.cmd_line_mode:
            self.send_command(sys.argv[1:])
            self.core.add_timeout(2, self.timeout_handler)
        else:
            self.console_thread = ConsoleThread(self)
            self.console_thread.start()

    def terminate(self):
        if self.console_thread:
            self.console_thread.terminate()

    def process_command_response(self, args, host, plugin):
        for line in args:
            print ("%10s@%-10s > %s" % (plugin, host, line))

    def timeout_handler(self):
        self.core.terminate()

descriptor = {
    'name' : 'cli',
    'mode' : PluginMode.MANUAL,
    'class' : CliPlugin
}
