import threading
import sys
import readline
import os
import atexit

from james.plugin import *


class ConsoleThread(threading.Thread):

    def __init__(self, plugin):
        super(ConsoleThread, self).__init__()
        self.plugin = plugin
        self.terminated = False
        self.logger = self.plugin.utils.get_logger('thread', self.plugin.logger)
        self.name = "ConsoleThread: %s" % self.__class__.__name__

        self.keywords = []

        if sys.platform == 'darwin':
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")

        readline.set_completer(self.complete)

        history_file = os.path.join(os.path.expanduser("~"), ".james_cli_history")
        try:
            readline.read_history_file(history_file)
        except IOError:
            pass

        atexit.register(readline.write_history_file, history_file)

    def run(self):

        self.logger.info("Interactive cli interface to JamesII (%s:%s) online." % (
            self.plugin.core.broker_config['host'],
            self.plugin.core.broker_config['port']))

        while not self.terminated:
            self.plugin.worker_lock.acquire()
            if self.plugin.worker_exit:
                self.plugin.worker_lock.release()
                self.terminated = True
                break
            else:
                self.plugin.worker_lock.release()

            # check for keyboard interrupt
            try:
                line = input()
            except KeyboardInterrupt:
                # http://bytes.com/topic/python/answers/43936-canceling-interrupting-raw_input
                self.plugin.core.add_timeout(0, self.plugin.core.terminate)
                self.terminated = True
                continue
            except EOFError:
                self.plugin.core.add_timeout(0, self.plugin.core.terminate)
                self.terminated = True
                continue

            line = line.strip()

            if len(line.rstrip()) > 0:
                args = line.split()

                if not self.plugin.commands.process_args(args):
                    if args[0] in self.plugin.core.config['core']['command_aliases']:
                        self.plugin.send_command(args)
                    elif str(self.plugin.core.data_commands.get_best_match(args)) != 'data':
                        self.plugin.send_command(args)
                    else:
                        best_match = self.plugin.core.ghost_commands.get_best_match(args)
                        if best_match == self.plugin.core.ghost_commands:
                            self.plugin.commands.process_args(['help_text'] + args)
                        else:
                            if len(best_match.subcommands) > 0:
                                self.plugin.commands.process_args(['help_text'] + args)
                            else:
                                self.plugin.send_command(args)
            else:
                print("Enter 'help' for a list of available commands.")

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
                    if len(args) == 1:
                        self.keywords += self.plugin.core.config['core']['command_aliases']

                # keep keywords that start with correct text
                args.append('')
                self.keywords = [name for name in self.keywords if name.startswith(args[0])]
                self.keywords = [name + " " for name in self.keywords]

                return self.keywords[0] if len(self.keywords) > 0 else None
            else:
                return self.keywords[state] if len(self.keywords) > state else None

        except Exception as e:
            print(e.__repr__())


class CliPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(CliPlugin, self).__init__(core, descriptor)

        self.console_thread = None
        self.cmd_line_mode = len(sys.argv) > 1
        self.worker_exit = False
        self.worker_lock = threading.Lock()

        self.commands.hide = True
        self.commands.create_subcommand('exit', 'Quits the console', self.cmd_exit)
        self.commands.create_subcommand('help', 'List this help', self.cmd_help)
        self.commands.create_subcommand('msg', 'Sends a msg (head[;body])', self.cmd_message)
        self.commands.create_subcommand('nodes', 'Show the local known nodes', self.cmd_nodes_online)
        self.commands.create_subcommand('allstatus', 'Request all node states', self.cmd_request_nodes_details)
        self.commands.create_subcommand('broadcast', 'Send test broadcast msg', self.cmd_send_broadcast)

    def start(self):
        if self.cmd_line_mode:
            self.logger.info('Sending command: %s' % ' '.join(sys.argv[1:]))
            self.send_command(sys.argv[1:])
            self.core.add_timeout(0, self.timeout_handler)
        else:
            self.console_thread = ConsoleThread(self)
            self.console_thread.start()

    def terminate(self):
        self.worker_lock.acquire()
        self.worker_exit = True
        self.worker_lock.release()

        if self.console_thread:
            self.console_thread.terminate()

    def cmd_request_nodes_details(self, args):
        self.send_command(['sys', 'allstatus'])

    def cmd_send_broadcast(self, args):
        self.send_broadcast('test me')

    def process_command_response(self, args, host, plugin):
        for line in args:
            print(("D%11s@%-10s > %s" % (plugin, host, line)))

    def process_broadcast_command_response(self, args, host, plugin):
        for line in args:
            print(("B%11s@%-10s > %s" % (plugin, host, line)))

    def timeout_handler(self):
        self.core.terminate()

    # commands
    def cmd_nodes_online(self, args):
        for node in sorted(self.core.nodes_online):
            if self.core.uuid == node:
                temp_str = "(cli)"
            elif self.core.master_node == node:
                temp_str = "(master)"
            else:
                temp_str = ""
            print(("%-10s %-8s %s" % (self.core.nodes_online[node], temp_str, node)))
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
            return "Message header: %s; body: %s" % (message.header, message.body)
        except Exception as e:
            return "Message could not me sent (%s)" % e

    def cmd_help(self, args):

        if len(args) > 0:
            command = self.core.ghost_commands.get_best_match(args)
            if command:
                if command.help:
                    print(("%s:" % command.help))
                self.print_command_help_lines(command)
            else:
                print("Command not found")

        else:
            print(("%-20s %s" % ('Command:', 'Description:')))

            print(("%-20s %s" % ('+', 'Local CLI Commands')))
            self.print_command_help_lines(self.commands, 1)

            print(("%-20s %s" % ('+', 'Remote Commands')))
            self.print_command_help_lines(self.core.ghost_commands, 1)

            print(("%-20s %s" % ('+', 'Command Aliases')))
            for command in sorted(self.core.config['core']['command_aliases'].keys()):
                print("|- %-17s %s" % (command, self.core.config['core']['command_aliases'][command]))

        return True

    def print_command_help_lines(self, command_obj, depth=0):
        for command in sorted(command_obj.subcommands.keys()):
            c = command_obj.subcommands[command]
            if not c.hide:
                print(("|%-19s %s" % (depth * "-" + " " + c.name, c.help)))
                if len(list(c.subcommands.keys())) > 0:
                    self.print_command_help_lines(c, depth + 1)
        return True


descriptor = {
    'name': 'cli',
    'help_text': 'Command line interface plugin',
    'command': 'cli',
    'mode': PluginMode.MANUAL,
    'class': CliPlugin,
    'detailsNames': {}
}
