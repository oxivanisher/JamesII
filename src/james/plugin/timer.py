
import os
import sys
import time
import atexit
import json
import re
import pytz
import datetime

from james.plugin import *

class TimerPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(TimerPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('at', 'Runs a command at given time (hh:mm[:ss] [dd-mm-yyyy])', self.cmd_timer_at)
        self.commands.create_subcommand('remove', 'Delets a command (id)', self.cmd_timer_remove)
        self.commands.create_subcommand('in', 'Runs a command in given time (sec|1s2m3h4d5w)', self.cmd_timer_in)
        self.commands.create_subcommand('show', 'Returns a list of commands', self.cmd_timer_show)

        self.command_cache_file = os.path.join(os.path.expanduser("~"), ".james_timer_store")
        atexit.register(self.save_commands)

        self.saved_commands = []
        self.load_saved_commands()

        self.load_state('commandsRun', 0)

    def start(self):
        # wait 3 seconds befor working
        self.core.add_timeout(3, self.command_daemon_loop)

    def load_saved_commands(self):
        try:
            file = open(self.command_cache_file, 'r')
            # self.saved_commands = self.utils.convert_from_unicode(json.loads(file.read()))
            self.saved_commands = json.loads(file.read())
            file.close()
            self.logger.debug("Loading timed commands from %s" % (self.command_cache_file))
        except IOError:
            pass
        pass

    def save_commands(self):
        try:
            file = open(self.command_cache_file, 'w')
            file.write(json.dumps(self.saved_commands))
            file.close()
            self.logger.debug("Saving timed commands to %s" % (self.command_cache_file))
        except IOError:
            self.logger.warning("Could not save cached commands to file!")

    # command methods
    def cmd_timer_in(self, args):
        (seconds, newArgs) = self.utils.duration_string2seconds(args)
        if seconds > 0:
            target_time = int(time.time()) + seconds
            return [self.timer_at(target_time, newArgs)]
        else:
            return ["Invalid syntax. Use seconds or: 3d4h3m2s"]

    def cmd_timer_at(self, args):
        timezone = pytz.timezone(self.core.config['core']['timezone'])
        target_time = datetime.datetime.now(timezone)
        day = 0
        month = 0
        year = 0
        target_timestamp = None
        try:
            target_timestamp = int(args[0])
            args = args[1:]
        except Exception as e:
            pass

        if not target_timestamp:
            try:
                time_sec = self.utils.time_string2seconds(args[0])
                hour = int(time_sec / 3600)
                minute = int((time_sec - hour * 3600) / 60)
                second = int(time_sec % 60)
                target_time = target_time.replace(hour   = hour)
                target_time = target_time.replace(minute = minute)
                target_time = target_time.replace(second = second)
                args = args[1:]
            except Exception as e:
                pass

            try:
                time_date = self.utils.date_string2values(args[0])
                target_time = target_time.replace(year  = time_date[0])
                target_time = target_time.replace(month = time_date[1])
                target_time = target_time.replace(day   = time_date[2])
                args = args[1:]
            except Exception as e:
                pass

            target_timestamp = int(target_time.strftime('%s'))

        if target_timestamp > 0 and len(args) > 0:
            if target_timestamp < time.time():
                target_timestamp += 86400
            return [self.timer_at(target_timestamp, args)]
        else:
            return ["Invalid syntax. Use timestamp or hh:mm[:ss] [dd-mm-yyyy]"]

    def cmd_timer_show(self, args):
        ret = []
        for (timestamp, command) in self.saved_commands:
            ret.append("(%s) %s: %s" % (timestamp,
                                        self.utils.get_nice_age(timestamp),
                                        ' '.join(command)))
        if len(ret) > 0:
            return ret
        else:
            return ["No commands found"]

    def cmd_timer_remove(self, args):
        ret = "Command not found"
        saved_commands_new = []
        for (timestamp, command) in self.saved_commands:
            try:
                if timestamp == int(args[0]) and command == args[1:]:
                    ret = (['Removed Command %s' % (' '.join(args))])
                else:
                    saved_commands_new.append((timestamp, command))
            except IndexError:
                ret = (['Command not found. Use syntax: mcp remove TIMESTAMP COMMAND'])
            except ValueError:
                ret = (['Wrong use of command. Use: mcp remove TIMESTAMP COMMAND'])
        self.saved_commands = saved_commands_new
        return ret

    # internal timer methods
    def timer_at(self, timestamp, command):
        # self.saved_commands.append(( timestamp, self.utils.list_unicode_cleanup(command) ))
        self.logger.info('Saved command (%s) %s with timestamp (%s)' % (' '.join(command), self.utils.get_nice_age(timestamp), timestamp))
        self.saved_commands.append(( timestamp, command ))
        return("Saved Command (%s) %s" % (' '.join(command),
                                          self.utils.get_nice_age(timestamp)))

    def command_daemon_loop(self):
        now = int(time.time())
        saved_commands_new = []
        for (timestamp, command) in self.saved_commands:
            if timestamp <= now:
                self.commandsRun += 1
                self.send_command(command)
                self.logger.info('Running timed command (%s)' % (' '.join(command)))
            else:
                saved_commands_new.append((timestamp, command))

        self.saved_commands = saved_commands_new
        self.core.add_timeout(1, self.command_daemon_loop)

    def return_status(self):
        ret = {}
        ret['waitingCommands'] = len(self.saved_commands)
        ret['commandsRun'] = self.commandsRun
        return ret

descriptor = {
    'name' : 'timer',
    'help' : 'MASTER CONTROL PROGRAM for timed functions',
    'command' : 'mcp',
    'mode' : PluginMode.MANAGED,
    'class' : TimerPlugin,
    'detailsNames' : { 'waitingCommands' : "Waiting commands",
                       'commandsRun' : "Commands run" }
}

