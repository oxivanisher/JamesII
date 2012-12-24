
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

        self.fade_in_progress = False

        if self.core.config['mpd']['host']:
            self.connection_string.append('--host=' + self.core.config['mpd']['host'])
        if self.core.config['mpd']['port']:
            self.connection_string.append('--port=' + self.core.config['mpd']['port'])
        if self.core.config['mpd']['password']:
            self.connection_string.append('--password=' + self.core.config['mpd']['password'])

        if os.path.isfile(self.mpc_bin):
            self.commands.create_subcommand('mpc', 'call mpc with given args', self.mpc)
            talkover_command = self.commands.create_subcommand('talkover', 'on or off for talkover', None)
            talkover_command.create_subcommand('on', 'avtivate talkover', self.activate_talkover)
            talkover_command.create_subcommand('off', 'deavtivate talkover', self.deactivate_talkover)
            self.commands.create_subcommand('on', 'turn on the radio', self.radio_on)
            self.commands.create_subcommand('off', 'turn off the radio', self.radio_off)
            if os.path.isfile('/usr/bin/mpfade'):
                self.commands.create_subcommand('sleep', 'run the mpd sleep script', self.mpd_sleep)
                self.commands.create_subcommand('wakeup', 'run the mpd wakeup script', self.mpd_wakeup)

    def mpc(self, args):
        return self.exec_mpc(args)

    def activate_talkover(self, args):
        self.exec_mpc(['volume', str(self.core.config['mpd']['talk_volume'])])

    def deactivate_talkover(self, args):
        self.exec_mpc(['volume', str(self.core.config['mpd']['max_volume'])])

    def radio_off(self, args):
        message = self.core.new_message(self.name)
        message.header = "MPC: Radio off"
        message.level = 1
        message.send()

        self.exec_mpc(['clear'])

    def radio_on(self, args):
        message = self.core.new_message(self.name)
        message.header = "MPC: Radio on"
        message.level = 1
        message.send()

        self.load_online_playlist(self.core.config['mpd']['radio_url'])
        self.exec_mpc(['volume', str(self.core.config['mpd']['max_volume'])])
        self.exec_mpc(['play'])     

    def mpd_sleep(self, args):
        if not self.fade_in_progress:
            message = self.core.new_message(self.name)
            message.header = "MPC: Sleep mode enabled"
            message.level = 1
            message.send()

            self.fade_in_progress = True
            self.core.spawnSubprocess(self.mpd_sleep_worker, self.mpd_callback)
        else:
            message = self.core.new_message(self.name)
            message.header = "MPC: Sleep mode NOT enabled. Fade already in progress..."
            message.level = 1
            message.send()

    def mpd_sleep_worker(self):
        self.load_online_playlist(self.core.config['mpd']['sleep_url'])
        self.exec_mpc(['play'])
        command = ['/usr/bin/mpfade',
                   str(self.sleep_fade_time),
                   "0",
                   self.core.config['mpd']['host']]
        args = self.core.utils.list_unicode_cleanup(command)
        self.core.popenAndWait(args)

    def mpd_wakeup(self, args):
        if not self.fade_in_progress:
            message = self.core.new_message(self.name)
            message.header = "MPC: Wakeup mode enabled"
            message.level = 1
            message.send()

            self.fade_in_progress = True
            self.core.spawnSubprocess(self.mpd_wakeup_worker, self.mpd_callback)
        else:
            message = self.core.new_message(self.name)
            message.header = "MPC: Sleep mode NOT enabled. Fade already in progress..."
            message.level = 1
            message.send()

    def mpd_wakeup_worker(self):
        self.exec_mpc(['clear'])
        self.load_online_playlist(self.core.config['mpd']['radio_url'])

        command = ['/usr/bin/mpfade',
                   str(self.wakeup_fade_time),
                   self.core.config['mpd']['radio_url'],
                   self.core.config['mpd']['host']]
        args = self.core.utils.list_unicode_cleanup(command)
        self.core.popenAndWait(args)

    def mpd_callback(self, values):
        self.fade_in_progress = False

    # Helper Methods
    def exec_mpc(self, args):
        args = self.core.utils.list_unicode_cleanup(self.connection_string + args)
        mpc = self.core.popenAndWait(args)

        message = self.core.new_message(self.name)
        message.header = "MPC: " + ' '.join(args)
        message.body = mpc
        message.send()

        return mpc

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

