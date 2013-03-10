
import os
import sys
import urllib2
import subprocess
import time
import mpd

from james.plugin import *

#FIXME: ToDo
# - better status command output
# - what happens when mpd disconnects?
# - command to set volume

class MpdClientWorker(object):
    # FIXME: make me singleton!

    def __init__(self, plugin, myhost, myport):
        self.connected = False
        self.plugin = plugin
        self.myhost = myhost
        self.myport = myport
        self.pretalk_volume = None
        self.worker_lock = threading.Lock()

        self.client = mpd.MPDClient(use_unicode=False)
        try:
            self.client.connect(self.myhost, self.myport)
            self.connected = True
        except Exception as e:
            print "connection error (%s)" % e
            pass

        self.client.timeout = 10

    def lock(self):
        # print "    locking"
        self.worker_lock.acquire()
        # print "    locked"

    def unlock(self):
        # print "    unlocking"
        self.worker_lock.release()
        # print "    unlocked"

    def play_url(self, uri, volume = None):
        self.lock()
        self.client.command_list_ok_begin()

        if volume:
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
            return True
        else:
            return False

    def stop(self):
        self.lock()
        self.plugin.fade_in_progress = False
        self.client.stop()
        self.unlock()

    def clear(self):
        self.lock()
        self.plugin.fade_in_progress = False
        self.client.clear()
        self.unlock()

    def status(self):
        self.lock()
        tmp_status = self.client.status()
        self.unlock()
        return tmp_status

    def setvol(self, volume):
        print "set volume (%s)" % volume
        self.lock()
        self.client.setvol(volume)
        self.unlock()

    def disconnect(self):
        self.lock()
        self.fade_in_progress = False
        self.client.close()
        self.client.disconnect()
        self.unlock()


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

        # print "fade thread startet (vol: %s)" % self.start_volume

        # self.work()

    def work(self):
        # print("fading started working")

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

        # print "increase : %s" % increase
        # print "fade_time: %s" % self.fade_time
        # print "vol_steps: %s" % vol_steps
        # print "step_wait: %s" % step_wait

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
        # print "on exit"
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
        self.pretalk_volume = self.client_worker.status()['volume']
        self.client_worker.setvol(self.core.config['mpd-client']['talk_volume'])
        return (["Activate talkover"])

    def deactivate_talkover(self, args):
        self.client_worker.setvol(self.pretalk_volume)
        self.pretalk_volume = None
        return (["Deactivate talkover"])

    def show_status(self, args):
        status = self.client_worker.status()
        return "[%s] %s at %s%" % (status['state'], status['song'], status['volume'])
        pass

    def radio_off(self, args):
        self.send_broadcast(['Stopping radio'])
        self.client_worker.stop()
        self.client_worker.clear()
        return (["Radio off"])

    def radio_on(self, args):
        self.client_worker.lock()
        self.fade_in_progress = False
        self.client_worker.unlock()
        self.send_broadcast(['Starting radio'])
        self.client_worker.play_url(self.core.config['mpd-client']['radio_url'],
                                    self.core.config['mpd-client']['norm_volume'])
        return (["Radio on"])

    def radio_toggle(self, args):
        self.send_broadcast(['Radio toggle'])
        if self.client_worker.status()['state'] == 'play':
            self.radio_off(args)
        else:
            self.radio_on(args)
        return (["Toggling radio"])

    def mpd_sleep(self, args):
        self.send_broadcast(['MPD Sleeping activated'])
        self.radio_off(None)
        self.client_worker.play_url(self.core.config['mpd-client']['sleep_url'],
                                int(self.core.config['mpd-client']['norm_volume']) - 30)

        self.thread = FadeThread(self,
                                 self.client_worker,
                                 self.core.config['mpd-client']['sleep_fade'],
                                 0)
        self.thread.start()

        if self.fade_in_progress:
            return (["MPD Sleep mode NOT activated due other fade in progress"])
        else:
            return (["MPD Sleep mode activated"])

    def mpd_wakeup(self, args):
        self.send_broadcast(['MPD Wakeup activated'])
        self.radio_off(None)
        self.client_worker.play_url(self.core.config['mpd-client']['wakeup_url'], 0)

        self.thread = FadeThread(self,
                                 self.client_worker,
                                 self.core.config['mpd-client']['wakeup_fade'],
                                 self.core.config['mpd-client']['norm_volume'])
        self.thread.start()

        if self.fade_in_progress:
            return (["MPD Wakeup mode NOT activated due other fade in progress"])
        else:
            return (["MPD Wakeup mode activated"])

    def fade_ended(self):
        # print "fade ending"
        self.client_worker.lock()
        self.fade_in_progress = False
        self.client_worker.unlock()
        if int(self.client_worker.status()['volume']) == 0:
            self.client_worker.stop()
            self.client_worker.clear()
        # print "fade ended"

    # react on proximity events
    def process_proximity_event(self, newstatus):
        if (time.time() - self.core.startup_timestamp) > 10:
            if self.core.config['core']['debug']:
                print("MPD Processing proximity event")
            if newstatus['status'][self.core.location]:
                self.radio_on(None)
            else:
                self.radio_off(None)

descriptor = {
    'name' : 'mpd-client',
    'help' : 'Interface to mpd via mpc',
    'command' : 'mpd',
    'mode' : PluginMode.MANAGED,
    'class' : MpdClientPlugin
}
