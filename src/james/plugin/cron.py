
import os
import sys
import time
import atexit
import json
import random
import string
from datetime import datetime, timedelta

from james.plugin import *

# from: http://stackoverflow.com/questions/373335/suggestions-for-a-cron-like-scheduler-in-python
# Some utility classes / functions first
class AllMatch(set):
    """Universal set - match everything"""
    def __contains__(self, item): return True

allMatch = AllMatch()

def conv_to_set(obj):  # Allow single integer to be provided
    if isinstance(obj, (int,long)):
        return set([obj])  # Single item
    if not isinstance(obj, set):
        obj = set(obj)
    return obj

# The actual CronEvent class
class CronEvent(object):
    def __init__(self, action, min=allMatch, hour=allMatch, 
                       day=allMatch, month=allMatch, dow=allMatch, 
                       args=(), kwargs={}):
        self.mins = conv_to_set(min)
        self.hours= conv_to_set(hour)
        self.days = conv_to_set(day)
        self.months = conv_to_set(month)
        self.dow = conv_to_set(dow)
        self.action = action
        self.args = args
        self.kwargs = kwargs

    def matchtime(self, t):
        """Return True if this event should trigger at the specified datetime"""
        return ((t.minute     in self.mins) and
                (t.hour       in self.hours) and
                (t.day        in self.days) and
                (t.month      in self.months) and
                (t.weekday()  in self.dow))

    def check(self, t):
        if self.matchtime(t):
            self.action(*self.args, **self.kwargs)

    def show(self):
        ret = {}
        ret['mins'] = self.mins
        ret['hours'] = self.hours
        ret['days'] = self.days
        ret['months'] = self.months
        ret['dow'] = self.dow
        ret['cmd'] = self.args

        return ret

# crontab class
class CronTab(object):
    def __init__(self):
        self.events = []

    def run(self):
        t=datetime(*datetime.now().timetuple()[:5])
        for e in self.events:
            e.check(t)

    def add_event(self, event):
        self.events.append(event)

    def show(self):
        ret = []
        ret_format = '%-3s %-7s %-7s %-7s %-7s %-7s %s'
        ret.append(ret_format % ('id', 'mins', 'hours', 'days', 'months', 'dow', 'command'))
        for e in self.events:
            event_data = e.show()
            for key in event_data.keys():
                if event_data[key] == AllMatch():
                    event_data[key] = "*"
                elif len(event_data[key]) > 0:
                    if key == 'cmd':
                        event_data[key] = ' '.join(event_data[key])
                    else:
                        event_data[key] = ','.join(event_data[key])

            ret.append(ret_format % (self.events.index(e),
                                     event_data['mins'],
                                     event_data['hours'],
                                     event_data['days'],
                                     event_data['months'],
                                     event_data['dow'],
                                     event_data['cmd']))
        return ret

class CronPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(CronPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('add', 'adds a cron command', self.cmd_cron_add)
        self.commands.create_subcommand('show', 'shows the cron commands', self.cmd_cron_show)
        self.commands.create_subcommand('delete', 'delets a cron command', self.cmd_cron_delete)

        self.command_cron_file = os.path.join(os.path.expanduser("~"), ".james_crontab")
        atexit.register(self.save_commands)

        #FIXME add cron commands. each mon, di and so on
        # http://stackoverflow.com/questions/373335/suggestions-for-a-cron-like-scheduler-in-python
        self.load_saved_commands()
        self.crontab = CronTab()

        self.crontab_daemon_loop()

    def load_saved_commands(self):
        try:
            file = open(self.command_cron_file, 'r')
            # self.crontab = self.core.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
            # if self.core.config['core']['debug']:
            #     print("Loading timed commands from %s" % (self.command_cache_file))
        except IOError:
            pass
        pass

    def save_commands(self):
        try:
            file = open(self.command_cron_file, 'w')
            # file.write(json.dumps(self.crontab))
            file.close()
            # if self.core.config['core']['debug']:
            #     print("Loading timed commands from %s" % (self.command_cache_file))
        except IOError:
            print("WARNING: Could not safe cron commands to file!")

    # cron commands
    def cmd_cron_add(self, args):
        try:
            (cron_string, cmd_string) = ' '.join(args).split(';')
            cron_args = cron_string.split()
            cmd_args = cmd_string.split()

            newevent = CronEvent(self.run_crontab_command, cron_args, args=cmd_args)
            self.crontab.add_event(newevent)
            return("Command saved")
        except IndexError:
            return("Invalid syntax!")
        except ValueError:
            return("Invalid syntax!")

    def cmd_cron_show(self, args):
        return self.crontab.show()

    def cmd_cron_delete(self, args):
        #FIXME i do not work
        del_id = int(args[0])
        print("Removing ID %s" % (del_id))
        self.crontab.events.remove(del_id)
        try:
            del_id = int(args[0])
            self.crontab.events.remove(del_id)
        except Exception:
            return("Invalid syntax!")
        # ret = "Command not found"
        # saved_commands_new = []
        # for (timestamp, command) in self.saved_commands:
        #     if timestamp == int(args[0]) and command == args[1:]:
        #         ret = ('Removed Command %s' % (' '.join(args)))
        #     else:
        #         saved_commands_new.append((timestamp, command))
        # self.saved_commands = saved_commands_new
        # return ret

    # internal cron methods
    def run_crontab_command(self, *args, **kwargs):
        self.send_response(self.uuid,
                           'broadcast',
                           ('Running Command (%s)' % (' '.join(args))))
        self.send_command(args)

    def crontab_daemon_loop(self):
        self.crontab.run()
        seconds = int(time.time() % 60)
        self.core.add_timeout((60 - seconds), self.crontab_daemon_loop)

descriptor = {
    'name' : 'cron',
    'help' : 'cron daemon implementation',
    'command' : 'cron',
    'mode' : PluginMode.MANAGED,
    'class' : CronPlugin
}

