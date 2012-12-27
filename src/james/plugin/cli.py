
import threading
import sys
import yaml
import readline
import os
import atexit

import james.command


from james.plugin import *

class ConsoleThread(threading.Thread):

    def __init__(self, plugin):
        super(ConsoleThread, self).__init__()
        self.plugin = plugin
        self.terminated = False

        self.keywords = []

        if sys.platform == 'darwin':
            readline.parse_and_bind ("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
            
        readline.set_completer(self.complete)

        histfile = os.path.join(os.path.expanduser("~"), ".james_cli_history")
        try:
            readline.read_history_file(histfile)
        except IOError:
            pass

        atexit.register(readline.write_history_file, histfile)        

    def run(self):

        print("Interactive cli interface to JamesII (%s:%s) online." % (
                        self.plugin.core.brokerconfig['host'],
                        self.plugin.core.brokerconfig['port']))

        while (not self.terminated):
            try:
                line = raw_input()
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

    def complete(self, text, state):
        # catch exceptions
        try:
            line = readline.get_line_buffer()
            args = line.split(' ')

            if state == 0:
                self.keywords = []

                cmd = None
                cmd = self.plugin.commands.get_best_match(args)
                if cmd == self.plugin.commands:
                    cmd = self.plugin.core.ghost_commands.get_best_match(args)
                    if cmd == self.plugin.core.ghost_commands:
                        cmd = None

                if cmd:
                    args = args[cmd.get_depth():]
                    self.keywords = cmd.get_subcommand_names()
                else:
                    self.keywords = self.plugin.commands.get_subcommand_names()
                    self.keywords += self.plugin.core.ghost_commands.get_subcommand_names()

                # keep keywords that start with correct text
                args.append('')
                self.keywords = filter(lambda name: name.startswith(args[0]), self.keywords)
                self.keywords = map(lambda name: name + " ", self.keywords)

                return self.keywords[0] if len(self.keywords) > 0 else None
            else:
                return self.keywords[state] if len(self.keywords) > state else None

        except Exception, e:
            print e.__repr__()




class CliPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(CliPlugin, self).__init__(core, descriptor)

        self.console_thread = None
        self.cmd_line_mode = len(sys.argv) > 1

        self.commands.hide = True
        self.commands.create_subcommand('nodes', 'show the local nodes_online variables', self.cmd_nodes_online)
        self.commands.create_subcommand('prx', 'show the local proximity variables', self.cmd_prx)
        self.commands.create_subcommand('exit', 'quits the console', self.cmd_exit)
        self.commands.create_subcommand('msg', 'sends a message', self.cmd_message)
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
            print ("D%11s@%-10s > %s" % (plugin, host, line))

    def process_broadcast_command_response(self, args, host, plugin):
        for line in args:
            print ("B%11s@%-10s > %s" % (plugin, host, line))

    def timeout_handler(self):
        self.core.terminate()

    # commands
    def cmd_nodes_online(self, args):
        for node in self.core.nodes_online:
            if self.core.uuid == node:
                temp_str = "(cli)"
            elif self.core.master_node == node:
                temp_str = "(master)"
            else:
                temp_str = ""
            print("%-10s %-8s %s" % (self.core.nodes_online[node], temp_str, node))
        return True

    def cmd_prx(self, args):
        print("proximity_status : %s" % (self.core.proximity_status.get_all_status()))
        print("self.location : %s" % (self.core.location))
        return True

    def cmd_exit(self, args):
        self.core.terminate()
        return True

    def cmd_message(self, args):
        message_string = ' '.join(args)
        message_list = message_string.split(';')

        message = self.core.new_message("cli_message")
        message.level = 1
        try:
            message.body = message_list[1].strip()
        except IndexError:
            message.body = None

        try:
            message.header = message_list[0].strip()
            message.send()
            return ("Message header: %s; body: %s" % (msg.header, msg.body))
        except Exception as e:
            return ("Message could not me sent (%s)" % (e))

    def cmd_help(self, args):

        if len(args) > 0:    
            command = self.core.ghost_commands.get_best_match(args)
            if command:
                print("%s:" % (command.help))
                self.print_command_help_lines(command)
            else:
                print ("command not found")

        else:
            print("local commands:")
            self.print_command_help_lines(self.commands)

            print("remote commands:")
            self.print_command_help_lines(self.core.ghost_commands)

        return True

    def print_command_help_lines(self, command_obj):
        for command in command_obj.list():
            if not command['hide']:
                print ("%-15s - %s" % (command['name'], command['help']))

descriptor = {
    'name' : 'cli',
    'help' : 'command line interface plugin',
    'command' : 'cli',
    'mode' : PluginMode.MANUAL,
    'class' : CliPlugin
}
