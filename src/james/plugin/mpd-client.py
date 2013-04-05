
import os
import sys
import urllib2
import subprocess
import time
import mpd
import signal

from james.plugin import *

class MpdClientWorker(object):
    # FIXME: make me singleton!
    # FIXME: sometimes, i loose connection :()

    def __init__(self, plugin, myhost, myport):
        self.connected = False
        self.plugin = plugin
        self.myhost = myhost
        self.myport = myport
        self.pretalk_volume = None
        self.worker_lock = threading.Lock()
        signal.signal(signal.SIGALRM, self.sig_timeout_handler)

        self.client = mpd.MPDClient(use_unicode=False)
        self.logger = self.plugin.core.utils.getLogger('worker.%s' % int(time.time() * 100), self.plugin.logger)
        
        self.check_connection()

    def sig_timeout_handler(self, signum, frame):
        self.logger.warning('Lost connection to MPD server')
        self.connected = False
        self.unlock()
        pass

    def connect(self):
        self.logger.debug('Connecting to MPD server')
        try:
            self.lock()
            signal.alarm(5)
            self.client.connect(self.myhost, self.myport)
            self.unlock()
            signal.alarm(0)
            self.connected = True
            self.client.timeout = 10
            return True
        except Exception as e:
            signal.alarm(0)
            self.unlock()
            self.logger.error("Connection error (%s)" % e)
            pass

        return False

    def check_connection(self):
        self.logger.debug('Checking connection to MPD server')
        try:
            self.lock()
            signal.alarm(5)
            self.client.ping()
            self.unlock()
            signal.alarm(0)

            return True
        except mpd.ConnectionError:
            self.logger.debug('We are disconnected (ping)')
            signal.alarm(0)
            self.unlock()
            if self.connect():
                return True
            else:
                self.connected = False
                return False

    def lock(self):
        self.logger.debug('locking')
        self.worker_lock.acquire()

    def unlock(self):
        self.logger.debug('unlocking')
        self.worker_lock.release()

    def play_url(self, uri, volume = -1):
        self.logger.debug('Trying to play URI (%s) with volume (%s)' % (uri, volume))
        if self.check_connection():
            self.lock()
            self.client.command_list_ok_begin()

            if volume >= 0:
                self.client.setvol(volume)

            self.client.clear()

            url_found = False
            for source in urllib2.urlopen(uri):
                if source != "":
                    self.client.add(source.strip())
                    url_found = True

            if url_found:
                self.client.play()

            self.client.command_list_end()
            self.unlock()

            if url_found:
                self.logger.debug("Playing URI: %s" % uri)
                return True
            else:
                return False

    def play(self):
        if self.check_connection():
            self.lock()
            self.client.play()
            self.unlock()
            self.logger.debug("Playing")
            return True
        else:
            self.logger.debug("Unable to play")
            return False

    def stop(self):
        if self.check_connection():
            self.lock()
            self.plugin.fade_in_progress = False
            self.client.stop()
            self.unlock()
            self.logger.debug("Stoped")
            return True
        else:
            self.logger.debug("Unable to stop")
            return False

    def clear(self):
        if self.check_connection():
            self.lock()
            self.plugin.fade_in_progress = False
            self.client.clear()
            self.unlock()
            self.logger.debug("Cleared playlist")
            return True
        else:
            self.logger.debug("Unable to clear playlist")
            return False

    def status(self):
        if self.check_connection():
            self.lock()
            tmp_status = self.client.status()
            self.unlock()
            return tmp_status

    def currentsong(self):
        self.logger.debug('Fetching current song')
        if self.check_connection():
            self.lock()
            tmp_status = self.client.currentsong()
            self.unlock()
            return tmp_status

    def setvol(self, volume):
        if self.check_connection():
            self.lock()
            try:
                int(volume)
            except Exception:
                return False

            if volume >= 0 and volume <= 100:
                self.client.setvol(volume)
                self.unlock()
                self.logger.debug("Set volume to %s" % volume)
                return True
        else:
            self.logger.debug('Unable setting volume')
            return False

    def disconnect(self):
        self.lock()
        self.fade_in_progress = False
        self.connected = False
        try:
            self.client.close()
            self.client.disconnect()
        except mpd.ConnectionError:
            pass
        self.unlock()
        self.logger.debug("Disconnected")


class FadeThread(PluginThread):

    def __init__(self, plugin, mpd_client, fade_time, target_vol):
        super(FadeThread, self).__init__(plugin)
        self.mpd_client = mpd_client
        self.fade_time = fade_time
        self.target_vol = target_vol

        #calc fade_time
        self.mpd_client.lock()
        self.plugin.fade_in_progress = True
        self.mpd_client.unlock()
        self.start_volume = int(self.mpd_client.status()['volume'])
        self.last_vol = self.start_volume

        self.logger.debug("Fade initialized with volume %s" % self.start_volume)

        # self.work()

    def work(self):
        self.logger.debug("Fading started working")

        run = True
        loopcount = 0
        vol_steps = self.start_volume - int(self.target_vol)
        if vol_steps == 0:
            return
        elif vol_steps < 0:
            vol_steps = vol_steps * -1

        if self.start_volume < self.target_vol:
            increase = True
        else:
            increase = False

        step_wait = int((self.fade_time * 10) / vol_steps)

        step_count = 0

        while run:
            step_count += 1
            loopcount += 1

            self.mpd_client.lock()
            fade_state = self.plugin.fade_in_progress
            self.mpd_client.unlock()
            
            if not fade_state:
                return

            if step_count >= step_wait:
                if increase:
                    self.last_vol += 1
                else:
                    self.last_vol -= 1

                self.mpd_client.setvol(self.last_vol)
                step_count = 0

            if self.last_vol == self.target_vol:
                run = False

            time.sleep(0.1)

    def on_exit(self, result):
        self.plugin.fade_ended()

class MpdClientPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(MpdClientPlugin, self).__init__(core, descriptor)

        self.myhost = 'localhost'
        self.myport = 6600
        if self.core.config['mpd-client']['nodes'][self.core.hostname]['host']:
            self.myhost = self.core.config['mpd-client']['nodes'][self.core.hostname]['host']
        if self.core.config['mpd-client']['nodes'][self.core.hostname]['port']:
            self.myport = self.core.config['mpd-client']['nodes'][self.core.hostname]['port']
        # self.mypassword = self.core.config['mpd-client']['nodes'][self.core.hostname]['password']

        self.client_worker = MpdClientWorker(self, self.myhost, self.myport)
        self.fade_in_progress = False
        self.thread = None
        self.talkover_volume = self.core.config['mpd-client']['norm_volume']

        self.commands.create_subcommand('volume', 'Set the volume', self.cmd_set_volume)

        radio_command =  self.commands.create_subcommand('radio', 'Control the web radio', None)
        radio_command.create_subcommand('on', 'Turn the radio on', self.radio_on)
        radio_command.create_subcommand('off', 'Turn the radio off', self.radio_off)
        radio_command.create_subcommand('toggle', 'Toggles the radio on and off', self.radio_toggle)
        radio_command.create_subcommand('sleep', 'Start mpd sleep mode', self.mpd_sleep)
        radio_command.create_subcommand('wakeup', 'Start mpd wakup mode', self.mpd_wakeup)

        talkover_command = self.commands.create_subcommand('talkover', 'Lowers the volume output', None)
        talkover_command.create_subcommand('on', 'Activate talkover', self.activate_talkover)
        talkover_command.create_subcommand('off', 'Deavtivate talkover', self.deactivate_talkover)

        status_command = self.commands.create_subcommand('status', 'Shows the current MPD status', self.show_status)

    def terminate(self):
        self.client_worker.lock()
        self.fade_in_progress = False
        self.client_worker.unlock()
        self.client_worker.disconnect()

    def activate_talkover(self, args):
        self.logger.debug('Activating talkover')
        status = self.client_worker.status()
        if status['volume'] != self.core.config['mpd-client']['talk_volume']:
            self.talkover_volume = int(status['volume'])
        if self.client_worker.setvol(self.core.config['mpd-client']['talk_volume']):
            return (["Activate talkover"])
        else:
            return (["Unable to connect to MPD"])

    def deactivate_talkover(self, args):
        self.logger.debug('Deactivating talkover')
        if self.client_worker.setvol(self.talkover_volume):
            return (["Deactivate talkover"])
        else:
            return (["Unable to connect to MPD"])

    def show_status(self, args):
        self.logger.debug('Showing status')
        status = self.client_worker.status()
        currentsong = self.client_worker.currentsong()
        if not status and not currentsong:
            return (["Unable to connect to MPD"])

        str_status = status['state']
        name = "Nothing"
        title = ""

        if status['state'] == "play":
            str_status = "Playing"
            title = currentsong['title']
            name = " (" + currentsong['name'] + ")"
        elif status['state'] == "stop":
            str_status = "Stopped"
        elif status['state'] == "pause":
            str_status = "Paused"
            name = currentsong['name']

        return ("[%s@%s%%] %s%s" % (str_status, status['volume'], title, name))

    def radio_off(self, args):
        self.logger.debug('Radio off')
        if self.client_worker.stop():
            self.client_worker.clear()
            return (["Radio off"])
        else:
            return (["Unable to connect to MPD"])

    def radio_on(self, args):
        self.logger.debug('Radio on')
        self.client_worker.lock()
        self.fade_in_progress = False
        self.client_worker.unlock()
        if self.client_worker.play_url(self.core.config['mpd-client']['radio_url'],
                                    self.core.config['mpd-client']['norm_volume']):
            return (["Radio on"])
        else:
            return (["Unable to connect to MPD"])

    def radio_toggle(self, args):
        self.logger.debug('Radio toggle')
        tmp_state = self.client_worker.status()
        if tmp_state:
            if tmp_state['state'] == 'play':
                self.radio_off(args)
            elif tmp_state['state'] == 'paused':
                self.client_worker.play()
            else:
                self.radio_on(args)
            return (["Toggling radio"])
        else:
            return (["Unable to connect to MPD"])

    def cmd_set_volume(self, args):
        try:
            volume = int(args[0])
            if volume >= 0 and volume <= 100:
                if self.client_worker.setvol(volume):
                    return (["Volume set to: %s" % volume])
        except Exception:
            volume = None
            pass

        self.logger.debug("Unable to set the volume to: %s" % volume)
        return (["Unable to set the volume to: %s" % volume])

    def mpd_sleep(self, args):
        self.logger.debug('Activating sleep mode')
        if self.core.proximity_status.get_status_here():
            if self.fade_in_progress:
                self.logger.info("MPD Sleep mode NOT activated due other fade in progress")
            else:
                self.radio_off(None)
                self.client_worker.play_url(self.core.config['mpd-client']['sleep_url'],
                                        int(self.core.config['mpd-client']['norm_volume']) - 30)

                self.thread = FadeThread(self,
                                         self.client_worker,
                                         self.core.config['mpd-client']['sleep_fade'],
                                         0)
                self.thread.start()
                self.logger.info("MPD Sleep mode activated")
        else:
            self.logger.info("MPD Sleep mode not activated. You are not here.")

    def mpd_wakeup(self, args):
        self.logger.debug('Activating wakeup mode')
        if self.core.proximity_status.get_status_here():
            if self.fade_in_progress:
                self.logger.info("MPD Wakeup mode NOT activated due other fade in progress")
            else:
                self.radio_off(None)
                self.client_worker.play_url(self.core.config['mpd-client']['wakeup_url'], 0)

                self.thread = FadeThread(self,
                                         self.client_worker,
                                         self.core.config['mpd-client']['wakeup_fade'],
                                         self.core.config['mpd-client']['norm_volume'])
                self.thread.start()
                self.logger.info("MPD Wakeup mode activated")
        else:
            self.logger.info("Wakeup not activated. You are not here.")

    def fade_ended(self):
        self.logger.debug("Fade ending")
        self.client_worker.lock()
        self.fade_in_progress = False
        self.client_worker.unlock()
        if int(self.client_worker.status()['volume']) == 0:
            self.client_worker.stop()
            self.client_worker.clear()
        self.logger.debug("Fade ended")

    # react on proximity events
    def process_proximity_event(self, newstatus):
        if (time.time() - self.core.startup_timestamp) > 10:
            self.logger.debug("MPD Processing proximity event")
            if newstatus['status'][self.core.location]:
                self.radio_on(None)
            else:
                self.radio_off(None)

descriptor = {
    'name' : 'mpd-client',
    'help' : 'Interface to mpd via python-mpc2 lib',
    'command' : 'mpd',
    'mode' : PluginMode.MANAGED,
    'class' : MpdClientPlugin
}
