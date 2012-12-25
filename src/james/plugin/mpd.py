
import os
import sys
import urllib2
import subprocess

from james.plugin import *

class MpdPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(MpdPlugin, self).__init__(core, descriptor)

        self.mpc_bin = '/usr/bin/mpc'

        self.wakeup_fade_time = self.core.config['mpd']['wakeup_fade']
        self.sleep_fade_time = self.core.config['mpd']['sleep_fade']

        self.connection_string = []
        self.connection_string.append(self.mpc_bin)
        self.myhost = self.core.config['mpd']['nodes'][sPelf.core.hostname]['host']
        self.myport = self.core.config['mpd']['nodes'][self.core.hostname]['port']
        self.mypassword = self.core.config['mpd']['nodes'][self.core.hostname]['password']

        self.fade_in_progress = False

        if self.myhost:
            self.connection_string.append('--host=' + self.myhost)
        if self.myport:
            self.connection_string.append('--port=' + self.myport)
        if self.mypassword:
            self.connection_string.append('--password=' + self.mypassword)

        if os.path.isfile(self.mpc_bin):
            self.commands.create_subcommand('mpc', 'call mpc with given args', self.mpc)
            talkover_command = self.commands.create_subcommand('talkover', 'on or off for talkover', None)
            talkover_command.create_subcommand('on', 'avtivate talkover', self.activate_talkover)
            talkover_command.create_subcommand('off', 'deavtivate talkover', self.deactivate_talkover)
            radio_command =  self.commands.create_subcommand('radio', 'control the radio', None)
            radio_command.create_subcommand('on', 'turn on the radio', self.radio_on)
            radio_command.create_subcommand('off', 'turn off the radio', self.radio_off)
            if os.path.isfile('/usr/bin/mpfade'):
                radio_command.create_subcommand('sleep', 'run the mpd sleep script', self.mpd_sleep)
                radio_command.create_subcommand('wakeup', 'run the mpd wakeup script', self.mpd_wakeup)

    def mpc(self, args):
        return self.exec_mpc(args)

    def activate_talkover(self, args):
        self.exec_mpc(['volume', str(self.core.config['mpd']['talk_volume'])])
        return ("activate talkover")

    def deactivate_talkover(self, args):
        self.exec_mpc(['volume', str(self.core.config['mpd']['max_volume'])])
        return ("deactivate talkover")

    def radio_off(self, args):
        self.exec_mpc(['clear'])
        return ("radio off")

    def radio_on(self, args):
        self.load_online_playlist(self.core.config['mpd']['radio_url'])
        self.exec_mpc(['volume', str(self.core.config['mpd']['max_volume'])])
        self.exec_mpc(['play'])
        return ("radio on")


    def mpd_sleep(self, args):
        if not self.fade_in_progress:
            self.fade_in_progress = True
            self.core.spawnSubprocess(self.mpd_sleep_worker, self.mpd_callback)
            return ("mpd sleep mode activated")
        else:
            return("mpd sleepmode NOT activated due other fade in progress")

    def mpd_sleep_worker(self):
        self.exec_mpc(['clear'])
        self.load_online_playlist(self.core.config['mpd']['sleep_url'])
        self.exec_mpc(['volume', str(self.core.config['mpd']['max_volume'] - 20)])
        self.exec_mpc(['play'])
        command = ['/usr/bin/mpfade',
                   str(self.sleep_fade_time),
                   '0',
                   self.myhost]
        args = self.core.utils.list_unicode_cleanup(command)
        self.core.utils.popenAndWait(args)

    def mpd_wakeup(self, args):
        if not self.fade_in_progress:
            self.fade_in_progress = True
            self.core.spawnSubprocess(self.mpd_wakeup_worker, self.mpd_callback)
            return ("mpd wakeup mode activated")
        else:
            return("mpd sleepmode NOT activated due other fade in progress")

    def mpd_wakeup_worker(self):
        self.exec_mpc(['clear'])
        self.load_online_playlist(self.core.config['mpd']['radio_url'])
        self.exec_mpc(['volume', '0'])
        command = ['/usr/bin/mpfade',
                   str(self.wakeup_fade_time),
                   str(self.core.config['mpd']['max_volume']),
                   self.myhost]
        args = self.core.utils.list_unicode_cleanup(command)
        self.core.utils.popenAndWait(args)

    def mpd_callback(self, values):
        self.send_response(self.uuid, self.name, 'mpd fading ended')
        self.fade_in_progress = False

    def process_proximity_event(self, newstatus):
        if newstatus['status'][self.core.location]:
            self.radio_on(None)
        else:
            self.radio_off(None)

    # Helper Methods
    def exec_mpc(self, args):
        args = self.core.utils.list_unicode_cleanup(self.connection_string + args)
        mpc = self.core.utils.popenAndWait(args)
        return self.core.utils.list_unicode_cleanup(mpc)

    def load_online_playlist(self, url):
        for source in urllib2.urlopen(url):
            if source != "":
                self.exec_mpc(['add', source])

descriptor = {
    'name' : 'mpd',
    'help' : 'interface to mpd via mpc',
    'command' : 'mpd',
    'mode' : PluginMode.MANAGED,
    'class' : MpdPlugin
}

