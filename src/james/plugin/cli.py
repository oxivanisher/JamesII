
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
                line = sys.stdin.readline()
            except KeyboardInterrupt:
                self.plugin.core.terminate()

            line = line.strip()

            if len(line.rstrip()) > 0:
                args = line.split(' ')

                if not self.plugin.commands.process_args(args):
                    self.plugin.send_command(args)
            else:
                print("enter 'help' for a list of available commands.")

    def terminate(self):
       self.terminated = True


class CliPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(CliPlugin, self).__init__(core, descriptor)

        self.console_thread = None
        self.cmd_line_mode = len(sys.argv) > 1

        self.commands.hide = True
        self.commands.create_subcommand('prx', 'show the local proximity variables', self.cmd_prx)
        self.commands.create_subcommand('prx_home', 'set the proximity system for: at home', self.cmd_prx_home)
        self.commands.create_subcommand('prx_away', 'set the proximity system for: away', self.cmd_prx_away)
        self.commands.create_subcommand('exit', 'quits the console', self.cmd_exit)
        self.commands.create_subcommand('dump_config', 'dumps the config', self.cmd_dump_config)
        self.commands.create_subcommand('message', 'sends a test message', self.cmd_message)
        self.commands.create_subcommand('help', 'list this help', self.cmd_help)

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

    # commands
    def cmd_prx(self, args):
        print("proximity_status : %s" % (self.core.proximity_status.get_all_status()))
        print("self.location : %s" % (self.core.location))

    def cmd_prx_home(self, args):
        self.core.proximity_status.set_status_here(True, 'cli')

    def cmd_prx_away(self, args):
        self.core.proximity_status.set_status_here(False, 'cli')

    def cmd_exit(self, args):
        self.core.terminate()

    def cmd_dump_config(self, args):
        print("dumping config:")
        print(yaml.dump(self.core.config))

    def cmd_message(self, args):
        print("sending test message")
        message = self.plugin.core.new_message("cli_test")
        message.body = "Test Body"
        message.header = "Test Head"
        message.level = 1
        message.send()

    def cmd_help(self, args):
        print("local commands:")
        for command in self.commands.list():
            if not command['hide']:
                print ("%-15s - %s" % (command['name'], command['help']))

        print("remote commands:")
        for command in self.core.ghost_commands.list():
            if not command['hide']:
                print ("%-15s - %s" % (command['name'], command['help']))


descriptor = {
    'name' : 'cli',
    'help' : 'command line interface plugin',
    'command' : 'cli',
    'mode' : PluginMode.MANUAL,
    'class' : CliPlugin
}
