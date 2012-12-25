
import os
import sys
import time
import atexit
import json
import random
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
        except IOError:
            pass
        pass

    def save_commands(self):
        try:
            file = open(self.command_cron_file, 'w')
            # file.write(json.dumps(self.crontab))
            file.close()
        except IOError:
            print("WARNING: Could not safe cron commands to file!")

    # cron commands
    def cmd_cron_add(self, args):
        try:
            cron_string = args[0]
            cmd = args[1:]
            print("1: %s; 2: %s" % (cron_string, cmd))

            newevent = CronEvent(self.run_crontab_command, args=cmd)
            self.crontab.add_event(newevent)
            return("Command saved")
            # return("please learn human for: %s" % (args[0]))
        except IndexError:
            return("Invalid syntax!")

    def cmd_cron_show(self, args):
        return("please learn human for: %s" % (args[0]))
        pass

    def cmd_cron_delete(self, args):
        return("please learn human for: %s" % (args[0]))
        pass

    # internal timer methods
    def run_crontab_command(self, *args, **kwargs):
        self.send_response(self.uuid,
                           self.name,
                           ('Running Command (%s)' % (' '.join(args))))
        # self.send_command(command)
        print("Crontab run_crontab_command (%s)" % (args))

    def crontab_daemon_loop(self):
        print("crontab run (%s)" % (int(time.time())))
        # rnd = random.randint(0, 59)
        # print("random sleep: %s" % (rnd))
        # time.sleep(rnd)

        self.crontab.run()
        seconds = int(time.time() % 60)
        # print("seconds sleep: %s (%s)" % (seconds, int(time.time())))

        self.core.add_timeout((60 - seconds), self.crontab_daemon_loop)
        pass

descriptor = {
    'name' : 'cron',
    'help' : 'cron daemon implementation',
    'command' : 'cron',
    'mode' : PluginMode.MANAGED,
    'class' : CronPlugin
}

