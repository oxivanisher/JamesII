
import os
import sys
import urllib2
import subprocess

from james.plugin import *

class MpdPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(MpdPlugin, self).__init__(core, descriptor)

        self.mpc_bin = '/usr/bin/mpc'

        self.connection_string = self.mpc_bin
        if self.core.config['mpd']['host']:
            self.connection_string += " --host=" + self.core.config['mpd']['host']
        if self.core.config['mpd']['port']:
            self.connection_string += " --port=" + self.core.config['mpd']['port']
        if self.core.config['mpd']['password']:
            self.connection_string += " --password=" + self.core.config['mpd']['password']

        self.commands.create_subcommand('mpc', 'call mpc with given args', self.mpc)
        self.commands.create_subcommand('radio_on', 'turn on the radio', self.radio_on)
        self.commands.create_subcommand('radio_off', 'turn off the radio', self.radio_off)
        self.commands.create_subcommand('mpd_sleep', 'run the mpd sleep script', self.mpd_sleep)
        self.commands.create_subcommand('mpd_wakeup', 'run the mpd wakeup script', self.mpd_wakeup)

#if os.path.isfile(self.mpc_bin): FIXME
    def mpc(self, args):
        self.exec_mpc(args)

    def radio_off(self, args):
        message = self.core.new_message(self.name)
        message.header = "MPC: Radio off"
        message.level = 1
        message.send()

        self.exec_mpc(['clear'])

    # radio (online url) methods
#if self.core.config['mpd']['url'] != "":
    def radio_on(self, args):
        message = self.core.new_message(self.name)
        message.header = "MPC: Radio on"
        message.level = 1
        message.send()

        self.load_online_playlist(self.core.config['mpd']['radio_url'])
        self.exec_mpc(['play'])     

    def mpd_sleep(self, args):
        message = self.core.new_message(self.name)
        message.header = "MPC: Sleep mode enabled"
        message.level = 1
        message.send()

        self.load_online_playlist(self.core.config['mpd']['sleep_url'])
        self.exec_mpc(['play'])
        minutes = 1
        try:
            minutes = args[0]
        except IndexError:
            pass
        subprocess.Popen(['/usr/bin/mpfade', str(minutes), "0", self.core.config['mpd']['host']])

    def mpd_wakeup(self, args):
        message = self.core.new_message(self.name)
        message.header = "MPC: Wakeup mode enabled"
        message.level = 1
        message.send()

        self.exec_mpc(['clear'])
        self.load_online_playlist(self.core.config['mpd']['wakeup_url'])
        minutes = 1
        try:
            minutes = args[0]
        except IndexError:
            pass
        subprocess.Popen(['/usr/bin/mpfade', str(minutes), "100", self.core.config['mpd']['host']])

    # Helper Methods
    def exec_mpc(self, args):
        mpc_pipe = os.popen(self.connection_string + ' ' + ' '.join(args),'r')
        mpc = mpc_pipe.read().strip()
        mpc_pipe.close()

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

