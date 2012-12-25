
import os
import sys
import time
import atexit
import json
# import psutil
# import datetime

from james.plugin import *

class TimerPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(TimerPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('in', 'runs a command in given time', self.cmd_timer_in)
        self.commands.create_subcommand('at', 'runs a command at given time', self.cmd_timer_at)
        periodic_command = self.commands.create_subcommand('periodic', 'manages periodic commands', None)
        periodic_command.create_subcommand('add', 'adds a periodic command', self.cmd_periodic_add)
        periodic_command.create_subcommand('show', 'shows the periodic commands', self.cmd_periodic_show)
        periodic_command.create_subcommand('delete', 'delets a periodic command', self.cmd_periodic_delete)
        self.commands.create_subcommand('show', 'returns a list of commands', self.cmd_timer_show)
        self.commands.create_subcommand('delete', 'delets a command', self.cmd_timer_delete)

        self.command_cache_file = os.path.join(os.path.expanduser("~"), ".james_saved_commands")
        self.command_periodic_file = os.path.join(os.path.expanduser("~"), ".james_periodic_commands")
        atexit.register(self.safe_requests)

        #FIXME add periodic commands. each mon, di and so on
        self.saved_commands = []
        self.periodic_commands = []
        self.load_saved_commands()

        self.command_daemon_loop()

    def load_saved_commands(self):
        #FIXME load saved commands from file and check for commands which should have been run
        try:
            file = open(self.command_cache_file, 'r')
            self.saved_commands = self.core.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
        except IOError:
            pass
        pass

        try:
            file = open(self.command_periodic_file, 'r')
            self.periodic_commands = self.core.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
        except IOError:
            pass
        pass

    def safe_requests(self):
        #FIXME load saved commands from file and check for commands which should have been run
        try:
            file = open(self.command_cache_file, 'w')
            file.write(json.dumps(self.saved_commands))
            file.close()
        except IOError:
            print("WARNING: Could not safe cached commands to file!")

        try:
            file = open(self.command_periodic_file, 'w')
            file.write(json.dumps(self.periodic_commands))
            file.close()
        except IOError:
            print("WARNING: Could not safe periodic commands to file!")

    # command methods
    def cmd_timer_in(self, args):
        try:
            now = int(time.time())
            target_time = now + int(args[0])
            return self.timer_at(target_time, args[1:])
        except ValueError:
            pass

        return("please learn human for: %s" % (args[0]))

    def cmd_timer_at(self, args):
        return("please learn human for: %s" % (args[0]))
        pass

    def cmd_timer_show(self, args):
        ret = []
        print("show timer (%s)" % (self.saved_commands))
        for (timestamp, command) in self.saved_commands:
            ret.append("%10s %-25s %s" % (timestamp,
                                           ' '.join(command),
                                           self.core.utils.get_nice_age(timestamp)))
        return ret

    def cmd_timer_delete(self, args):
        ret = "Command not found"
        saved_commands_new = []
        for (timestamp, command) in self.saved_commands:
            print("testing: %s=%s %s=%s" % (timestamp, args[0], command, args[1:]))
            if timestamp == int(args[0]) and command == args[1:]:
                ret = ('Removed Command %s' % (' '.join(args)))
            else:
                saved_commands_new.append((timestamp, command))
        self.saved_commands = saved_commands_new
        return ret

    # periodic commands
    def cmd_periodic_add(self, args):
        return("please learn human for: %s" % (args[0]))
        pass

    def cmd_periodic_show(self, args):
        return("please learn human for: %s" % (args[0]))
        pass

    def cmd_periodic_delete(self, args):
        return("please learn human for: %s" % (args[0]))
        pass

    # internal timer methods
    def timer_at(self, timestamp, command):
        print("0: %s, 1+: %s" % (timestamp, command))
        self.saved_commands.append(( timestamp, self.core.utils.list_unicode_cleanup(command) ))
        return("Saved Command (%s) %s" % (' '.join(command),
                                          self.core.utils.get_nice_age(timestamp)))

    def command_daemon_loop(self):
        now = int(time.time())
        saved_commands_new = []
        for (timestamp, command) in self.saved_commands:
            if timestamp <= now:
                self.send_command(command)
                self.send_response(self.uuid,
                                   self.name,
                                   ('Running Command (%s)' % (' '.join(command))))
            else:
                saved_commands_new.append((timestamp, command))

        self.saved_commands = saved_commands_new
        self.core.add_timeout(1, self.command_daemon_loop)

descriptor = {
    'name' : 'timer',
    'help' : 'master control program for timed functions',
    'command' : 'mcp',
    'mode' : PluginMode.MANAGED,
    'class' : TimerPlugin
}

