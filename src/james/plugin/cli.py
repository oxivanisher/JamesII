
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
        self.logger = self.plugin.core.utils.getLogger('thread', self.plugin.logger)
    
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

        self.logger.info("Interactive cli interface to JamesII (%s:%s) online." % (
                         self.plugin.core.brokerconfig['host'],
                         self.plugin.core.brokerconfig['port']))

        while (not self.terminated):
            self.plugin.worker_lock.acquire()
            if self.plugin.worker_exit:
                self.plugin.worker_lock.release()
                self.terminated = True
                sys.quit()
                break
            self.plugin.worker_lock.release()

            # check for keyboard interrupt
            try:
                line = raw_input()
            except KeyboardInterrupt:
                # http://bytes.com/topic/python/answers/43936-canceling-interrupting-raw_input
                self.plugin.core.add_timeout(0, self.plugin.core.terminate)
                self.terminated = True
                sys.quit()
                break

            line = line.strip()

            if len(line.rstrip()) > 0:
                args = line.split()

                if not self.plugin.commands.process_args(args):
                    if args[0] in self.plugin.core.config['core']['command_aliases']:
                        self.plugin.send_command(args)
                    else:
                        if self.plugin.core.data_commands.get_best_match(args) != self.plugin.core.data_commands:
                            best_match = self.plugin.core.ghost_commands.get_best_match(args)
                            if best_match == self.plugin.core.ghost_commands:
                                self.plugin.commands.process_args(['help'] + args)
                            else:
                                if len(best_match.subcommands) > 0:
                                    self.plugin.commands.process_args(['help'] + args)
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
        self.worker_exit = False
        self.worker_lock = threading.Lock()


        self.commands.hide = True
        self.commands.create_subcommand('exit', 'Quits the console', self.cmd_exit)
        self.commands.create_subcommand('help', 'List this help', self.cmd_help)
        self.commands.create_subcommand('msg', 'Sends a message (head[;body])', self.cmd_message)
        self.commands.create_subcommand('nodes', 'Show the local known nodes', self.cmd_nodes_online)
        self.commands.create_subcommand('details', 'Request detailed node informations', self.cmd_request_nodes_details)

    def start(self):
        if self.cmd_line_mode:
            self.send_command(sys.argv[1:])
            self.core.add_timeout(2, self.timeout_handler)
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
        self.send_data_command(['sys', 'details'])

    def process_command_response(self, args, host, plugin):
        for line in args:
            print ("D%11s@%-10s > %s" % (plugin, host, line))

    def process_data_response(self, args, host, plugin):
        print "*** Processing data response from %s@%s ***" % (plugin, host)
        if plugin == 'system':
            display_data = []
            mode = "Slave"
            if args['master']:
                mode = "Master"

            startup = self.core.utils.get_nice_age(int(args['startup_timestamp']))
            timedelay = time.time() - args['now']

            display_data.append(('FQDN', args['fqdn']))
            display_data.append(('Mode', mode))
            display_data.append(('UUID', args['uuid']))
            display_data.append(('IP', args['ip'][0]))
            display_data.append(('James Startup', startup))
            display_data.append(('Delay', '%s seconds' % timedelay))
            display_data.append(('Location', args['location']))
            display_data.append(('Platform', args['platform']))
            display_data.append(('OS Username', args['os_username']))

            for (key, value) in display_data:
                print "%-14s %s" % (key, value)

    def process_broadcast_command_response(self, args, host, plugin):
        for line in args:
            print ("B%11s@%-10s > %s" % (plugin, host, line))

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
            print("%-10s %-8s %s" % (self.core.nodes_online[node], temp_str, node))
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
            return ("Message header: %s; body: %s" % (message.header, message.body))
        except Exception as e:
            return ("Message could not me sent (%s)" % (e))

    def cmd_help(self, args):

        if len(args) > 0:    
            command = self.core.ghost_commands.get_best_match(args)
            if command:
                if command.help:
                    print("%s:" % (command.help))
                self.print_command_help_lines(command)
            else:
                print ("Command not found")

        else:
            print ("%-20s %s" % ('Command:', 'Description:'))

            print ("%-20s %s" % ('+', 'Local CLI Commands'))
            self.print_command_help_lines(self.commands, 1)

            print ("%-20s %s" % ('+', 'Remote Commands'))
            self.print_command_help_lines(self.core.ghost_commands, 1)

            print ("%-20s %s" % ('+', 'Command Aliases'))
            for command in sorted(self.core.config['core']['command_aliases'].keys()):
                print "|- %-17s %s" % (command, self.core.config['core']['command_aliases'][command])

        return True

    def print_command_help_lines(self, command_obj, depth = 0):
        for command in sorted(command_obj.subcommands.keys()):
            c = command_obj.subcommands[command]
            if not c.hide:
                print ("|%-19s %s" % (depth * "-" + " " + c.name, c.help))
                if len(c.subcommands.keys()) > 0:
                    self.print_command_help_lines(c, depth + 1)
        return True

descriptor = {
    'name' : 'cli',
    'help' : 'Command line interface plugin',
    'command' : 'cli',
    'mode' : PluginMode.MANUAL,
    'class' : CliPlugin
}
