
import os
import sys
import time
import atexit
import json

from james.plugin import *

class TimerPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(TimerPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('in', 'runs a command in given time', self.cmd_timer_in)
        self.commands.create_subcommand('at', 'runs a command at given time', self.cmd_timer_at)
        self.commands.create_subcommand('show', 'returns a list of commands', self.cmd_timer_show)
        self.commands.create_subcommand('delete', 'delets a command', self.cmd_timer_delete)

        self.command_cache_file = os.path.join(os.path.expanduser("~"), ".james_saved_commands")
        atexit.register(self.save_commands)

        self.saved_commands = []
        self.load_saved_commands()

        self.command_daemon_loop()

    def load_saved_commands(self):
        try:
            file = open(self.command_cache_file, 'r')
            self.saved_commands = self.core.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
            if self.core.config['core']['debug']:
                print("Loading timed commands from %s" % (self.command_cache_file))
        except IOError:
            pass
        pass

    def save_commands(self):
        try:
            file = open(self.command_cache_file, 'w')
            file.write(json.dumps(self.saved_commands))
            file.close()
            if self.core.config['core']['debug']:
                print("Saving timed commands to %s" % (self.command_cache_file))
        except IOError:
            print("WARNING: Could not save cached commands to file!")

    # command methods
    def cmd_timer_in(self, args):
        try:
            now = int(time.time())
            target_time = now + int(args[0])
            return self.timer_at(target_time, args[1:])
        except ValueError: 
            return("Invalid syntax. Use  %s" % (args[0]))

    def cmd_timer_at(self, args):

        #FIXME i do not exist!
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
            if timestamp == int(args[0]) and command == args[1:]:
                ret = ('Removed Command %s' % (' '.join(args)))
            else:
                saved_commands_new.append((timestamp, command))
        self.saved_commands = saved_commands_new
        return ret

    # internal timer methods
    def timer_at(self, timestamp, command):
        self.saved_commands.append(( timestamp, self.core.utils.list_unicode_cleanup(command) ))
        return("Saved Command (%s) %s" % (' '.join(command),
                                          self.core.utils.get_nice_age(timestamp)))

    def command_daemon_loop(self):
        now = int(time.time())
        saved_commands_new = []
        for (timestamp, command) in self.saved_commands:
            if timestamp <= now:
                self.send_response(self.uuid,
                                   'broadcast',
                                   ('Running timed command (%s)' % (' '.join(command))))
                self.send_command(command)
            else:
                saved_commands_new.append((timestamp, command))

        self.saved_commands = saved_commands_new
        self.core.add_timeout(1, self.command_daemon_loop)

descriptor = {
    'name' : 'timer',
    'help' : 'MASTER CONTROL PROGRAM for timed functions',
    'command' : 'mcp',
    'mode' : PluginMode.MANAGED,
    'class' : TimerPlugin
}

