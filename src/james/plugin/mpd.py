
import os
import sys
import urllib2
import subprocess
import time

from james.plugin import *

class FadeThread(PluginThread):

    def __init__(self, plugin, host, volume1, volume2, fade_time, url):
        super(FadeThread, self).__init__(plugin)
        self.host = host
        self.volume1 = str(volume1)
        self.volume2 = str(volume2)
        self.fade_time = str(fade_time)
        self.url = url

    def work(self):
        self.plugin.exec_mpc(['clear'])
        self.plugin.load_online_playlist(self.url)
        if self.volume1 > self.volume2:
            # sleep mode
            self.plugin.exec_mpc(['volume', self.volume1])
            self.plugin.exec_mpc(['play'])
        self.plugin.exec_mpc(['volume', self.volume1])
        command = ['/usr/bin/mpfade',
                   str(self.fade_time),
                   str(self.volume2),
                   self.host]
        args = self.plugin.core.utils.list_unicode_cleanup(command)
        self.plugin.core.utils.popenAndWait(args)
        return(["MPD Fade ended"])

    def on_exit(self, result):
        self.plugin.mpd_callback(result)

class MpdPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(MpdPlugin, self).__init__(core, descriptor)

        self.mpc_bin = '/usr/bin/mpc'

        self.connection_string = []
        self.connection_string.append(self.mpc_bin)
        self.myhost = self.core.config['mpd']['nodes'][self.core.hostname]['host']
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
            self.commands.create_subcommand('mpc', 'Call mpc with given args', self.mpc)
            radio_command =  self.commands.create_subcommand('radio', 'Control the web radio', None)
            radio_command.create_subcommand('on', 'Turn on the radio', self.radio_on)
            radio_command.create_subcommand('off', 'Turn off the radio', self.radio_off)
            if os.path.isfile('/usr/bin/mpfade'):
                radio_command.create_subcommand('sleep', 'Start mpd sleep mode', self.mpd_sleep)
                radio_command.create_subcommand('wakeup', 'Start mpd wakup mode', self.mpd_wakeup)
            talkover_command = self.commands.create_subcommand('talkover', 'Lowers the volume output', None)
            talkover_command.create_subcommand('on', 'Activate talkover', self.activate_talkover)
            talkover_command.create_subcommand('off', 'Deavtivate talkover', self.deactivate_talkover)

    def mpc(self, args):
        return self.exec_mpc(args)

    def activate_talkover(self, args):
        self.exec_mpc(['volume', str(self.core.config['mpd']['talk_volume'])])
        return (["Activate talkover"])

    def deactivate_talkover(self, args):
        self.exec_mpc(['volume', str(self.core.config['mpd']['max_volume'])])
        return (["Deactivate talkover"])

    def radio_off(self, args):
        self.exec_mpc(['clear'])
        return (["Radio off"])

    def radio_on(self, args):
        self.exec_mpc(['clear'])
        self.load_online_playlist(self.core.config['mpd']['radio_url'])
        self.exec_mpc(['volume', str(self.core.config['mpd']['max_volume'])])
        self.exec_mpc(['play'])
        return (["Radio on"])

    def mpd_sleep(self, args):
        if not self.fade_in_progress:
            self.fade_in_progress = True

            self.fade_thread = FadeThread(self,
                                          self.core.config['mpd']['nodes'][self.core.hostname]['host'],
                                          (self.core.config['mpd']['max_volume'] - 20),
                                          0,
                                          self.core.config['mpd']['sleep_fade'],
                                          self.core.config['mpd']['sleep_url'])
            self.fade_thread.run()
            return (["MPD Sleep mode activated"])
        else:
            return (["MPD Sleep mode NOT activated due other fade in progress"])

    def mpd_wakeup(self, args):
        if not self.fade_in_progress:
            self.fade_in_progress = True

            self.fade_thread = FadeThread(self,
                                          self.core.config['mpd']['nodes'][self.core.hostname]['host'],
                                          0,
                                          self.core.config['mpd']['max_volume'],
                                          self.core.config['mpd']['wakeup_fade'],
                                          self.core.config['mpd']['wakeup_url'])
            self.fade_thread.run()
            return (["MPD Wakeup mode activated"])
        else:
            return (["MPD Wakeup mode NOT activated due other fade in progress"])

    def mpd_callback(self, values):
        self.fade_in_progress = False
        self.send_broadcast(values)

    def process_proximity_event(self, newstatus):
        if (time.time() - self.core.startup_timestamp) > 10:
            if self.core.config['core']['debug']:
                print("MPD Processing proximity event")
            if newstatus['status'][self.core.location]:
                self.radio_on(None)
            else:
                self.radio_off(None)

    # Helper Methods
    def exec_mpc(self, args):
        try:
            args = self.core.utils.list_unicode_cleanup(self.connection_string + args)
            mpc = self.core.utils.popenAndWait(args)
            return self.core.utils.list_unicode_cleanup(mpc)
        except UnicodeDecodeError:
            return ["Invalid command"]

    def load_online_playlist(self, url):
        for source in urllib2.urlopen(url):
            if source != "":
                self.exec_mpc(['add', source])

descriptor = {
    'name' : 'mpd',
    'help' : 'Interface to mpd via mpc',
    'command' : 'mpd',
    'mode' : PluginMode.MANAGED,
    'class' : MpdPlugin
}

