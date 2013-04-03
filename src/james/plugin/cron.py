
import os
import sys
import time
import atexit
import json
import random
import string
import ast
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
        self.active = True

    def matchtime(self, t):
        """Return True if this event should trigger at the specified datetime"""
        return ((t.minute     in self.mins) and
                (t.hour       in self.hours) and
                (t.day        in self.days) and
                (t.month      in self.months) and
                (t.weekday()  in self.dow))

    def check(self, t):
        if self.active:
            if self.matchtime(t):
                self.action(*self.args, **self.kwargs)

    def show(self):
        ret = {}
        ret['act'] = self.active
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

    def activate_event(self, id):
        try:
            self.events[id].active = True
            return True
        except Exception as e:
            pass

    def deactivate_event(self, id):
        try:
            self.events[id].active = False
            return True
        except Exception as e:
            pass

    def show(self):
        ret = []
        ret_format = '%-3s %-3s %-7s %-7s %-7s %-7s %-7s %s'
        ret.append(ret_format % ('id', 'act', 'mins', 'hours', 'days', 'months', 'dow', 'command'))
        for e in self.events:
            event_data = e.show()
            for key in event_data.keys():
                if event_data[key] == AllMatch():
                    event_data[key] = "*"
                elif key == "act":
                    if event_data[key]:
                        event_data[key] = "+"
                    else:
                        event_data[key] = "-"
                elif len(event_data[key]) > 0:
                    if key == 'cmd':
                        event_data[key] = ' '.join(event_data[key])
                    else:
                        event_data[key] = ','.join(str(x) for x in event_data[key])

            ret.append(ret_format % (self.events.index(e),
                                     event_data['act'],
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

        self.commands.create_subcommand('add', 'Adds a cron command (*[*][*][*][*];cmd)', self.cmd_cron_add)
        self.commands.create_subcommand('remove', 'Removes a cron command (id)', self.cmd_cron_remove)
        self.commands.create_subcommand('show', 'Shows the cron commands', self.cmd_cron_show)
        self.commands.create_subcommand('activate', 'Activates a cron command (id)', self.cmd_cron_activate)
        self.commands.create_subcommand('deactivate', 'Deactivates a cron command (id)', self.cmd_cron_deactivate)

        self.crontab = CronTab()
        self.command_cron_file = os.path.join(os.path.expanduser("~"), ".james_crontab")
        self.cron_list = []
        self.load_saved_commands()
        atexit.register(self.save_commands)

    def start(self):
        # wait 3 seconds befor working
        self.core.add_timeout(1, self.crontab_daemon_loop)

    def save_commands(self):
        try:
            file = open(self.command_cron_file, 'w')
            file.write(json.dumps(self.cron_list))
            file.close()
            self.logger.debug("Saving crontab to %s" % (self.command_cron_file))
        except IOError:
            self.logger.warning("Could not safe cron tab to file!")

    def load_saved_commands(self):
        try:
            file = open(self.command_cron_file, 'r')
            # self.cron_list = self.core.utils.convert_from_unicode(json.loads(file.read()))
            self.cron_list = json.loads(file.read())
            file.close()
            self.logger.debug("Loading crontab from %s" % (self.command_cron_file))
            self.load_commands_from_cron_list()
        except IOError:
            pass
        pass

    def load_commands_from_cron_list(self):
        self.crontab = CronTab()
        new_cron_list = []
        ret = True
        # for cron_entry in self.core.utils.list_unicode_cleanup(self.cron_list):
        for cron_entry in self.cron_list:
            try:
                cron_data = cron_entry.split(';')
                if len(cron_data) > 1:
                    cron_string = cron_data[0].strip()
                    cmd_string = cron_data[1].strip()

                    cron_args = []
                    for arg in cron_string.split(' '):
                        if arg.isdigit():
                            cron_args.append(int(arg))
                        elif arg == '*':
                            cron_args.append(allMatch)
                        elif arg == '-':
                            cron_args.append([])
                        elif ',' in arg:
                            tmp_list = []
                            tmp_args = arg.split(',')
                            for tmp_arg in tmp_args:
                                tmp_list.append(int(tmp_arg))
                            cron_args.append(tmp_list)    
                        elif '-' in arg:
                            tmp_list = []
                            tmp_args = arg.split('-')
                            for tmp_num in range(int(tmp_args[0]), (int(tmp_args[1]) + 1)):
                                tmp_list.append(tmp_num)
                            cron_args.append(tmp_list)

                    cmd_args = cmd_string.split()

                    act_args = True
                    try:
                        act_string = cron_data[2].strip()
                        if act_string != "True":
                            act_args = False
                    except Exception as e:
                        pass

                    new_cron_list.append("%s;%s;%s" % (cron_string, cmd_string, act_args))
                    self.add_cron_job(cron_args, cmd_args, act_args)
                else:
                    ret = False
            except Exception as e:
                ret = False
                pass
        self.cron_list = new_cron_list
        return ret

    def add_cron_job(self, cron_args, cmd_args, act_args):
        try:
            newevent = CronEvent(self.run_crontab_command, *cron_args, args=cmd_args)
            if act_args:
                newevent.active = True
            else:
                newevent.active = False
            self.crontab.add_event(newevent)
        except Exception as e:
            self.logger.error("Error on adding cron command: %s" % (e))
            pass

    # cron commands
    def cmd_cron_add(self, args):
        if len(args) > 0:
            self.cron_list.append(' '.join(args))
            if self.load_commands_from_cron_list():
                return(["Command saved"])
        return(["Invalid Syntax. Use Unix style like: 30 12 * * *; sys plugins"])

    def cmd_cron_show(self, args):
        return self.crontab.show()

    def cmd_cron_remove(self, args):
        try:
            del_id = int(args[0])
            num_of_jobs = len(self.cron_list)
            del_data = self.cron_list[del_id]
            self.cron_list.remove(del_data)
            self.load_commands_from_cron_list()
            return(["Removed job: %s" % (del_data)])
        except Exception as e:
            return(["Invalid syntax (%s)" % (e)])

    def cmd_cron_activate(self, args):
        try:
            act_id = int(args[0])
            old_str = self.cron_list[act_id]
            old_data = old_str.split(";")
            new_data = "%s;%s;%s" % (old_data[0], old_data[1], "True")
            self.cron_list[act_id] = new_data
            self.crontab.activate_event(act_id)
            return(["Activated job: %s" % (act_id)])
        except Exception as e:
            return(["Invalid syntax (%s)" % (e)])

    def cmd_cron_deactivate(self, args):
        try:
            deact_id = int(args[0])
            old_str = self.cron_list[deact_id]
            old_data = old_str.split(";")
            new_data = "%s;%s;%s" % (old_data[0], old_data[1], "False")
            self.cron_list[deact_id] = new_data
            self.crontab.deactivate_event(deact_id)
            return(["Deactivated job: %s" % (deact_id)])
        except Exception as e:
            return(["Invalid syntax (%s)" % (e)])

    # internal cron methods
    def run_crontab_command(self, *args, **kwargs):
        self.logger.info('Running Command (%s)' % (' '.join(args)))
        self.send_command(args)

    def crontab_daemon_loop(self):
        self.crontab.run()
        seconds = int(time.time() % 60)
        self.core.add_timeout((60 - seconds), self.crontab_daemon_loop)

descriptor = {
    'name' : 'cron',
    'help' : 'Cron daemon implementation',
    'command' : 'cron',
    'mode' : PluginMode.MANAGED,
    'class' : CronPlugin
}

