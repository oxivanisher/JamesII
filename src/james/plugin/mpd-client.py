import signal
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import mpd
from james.plugin import *


class PersistentMPDClient(mpd.MPDClient):
    # this class is from here: https://github.com/bdutro/PersistentMPDClient/blob/master/PersistentMPDClient.py

    def __init__(self, my_socket=None, host=None, port=None):
        super(PersistentMPDClient, self).__init__()
        self.socket = my_socket
        self.host = host
        self.port = port

        self.do_connect()
        # get list of available commands from client
        self.command_list = self.commands()

        # commands not to intercept
        self.command_blacklist = ['ping']

        # wrap all valid MPDClient functions
        # in a ping-connection-retry wrapper
        for cmd in self.command_list:
            if cmd not in self.command_blacklist:
                if hasattr(super(PersistentMPDClient, self), cmd):
                    super_fun = super(PersistentMPDClient, self).__getattribute__(cmd)
                    new_fun = self.try_cmd(super_fun)
                    setattr(self, cmd, new_fun)
                else:
                    pass

    # create a wrapper for a function (such as an MPDClient
    # member function) that will verify a connection (and
    # reconnect if necessary) before executing that function.
    # functions wrapped in this way should always succeed
    # (if the server is up)
    # we ping first because we don't want to retry the same
    # function if there's a failure, we want to use the noop
    # to check connectivity
    def try_cmd(self, cmd_fun):
        def fun(*pargs, **kwargs):
            try:
                self.ping()
            except (mpd.ConnectionError, OSError) as e:
                self.do_connect()
            return cmd_fun(*pargs, **kwargs)

        return fun

    # needs a name that does not collide with parent connect() function
    def do_connect(self):
        try:
            try:
                self.disconnect()
            # if it's a TCP connection, we'll get a socket error
            # if we try to disconnect when the connection is lost
            except mpd.ConnectionError as e:
                pass
            # if it's a socket connection, we'll get a BrokenPipeError
            # if we try to disconnect when the connection is lost,
            # but we have to retry the disconnect, because we'll get
            # an "Already connected" error if we don't.
            # the second one should succeed.
            except BrokenPipeError as e:
                try:
                    self.disconnect()
                except Exception as e:
                    print("Second disconnect failed, yikes.")
                    print(e)
                    pass
            if self.socket:
                self.connect(self.socket, None)
            else:
                self.connect(self.host, self.port)
        except socket.error as e:
            print("Connection refused.")


class MpdClientWorker(object):
    def __init__(self, plugin, my_host, my_port):
        self.plugin = plugin
        self.my_host = my_host
        self.my_port = my_port
        self.pre_talk_volume = None
        self.worker_lock = threading.Lock()

        signal.signal(signal.SIGALRM, self.sig_timeout_handler)

        self.client = mpd.MPDClient(use_unicode=False)
        # self.client = PersistentMPDClient() # not working test. if it still crashes, needs to be tested
        self.logger = self.plugin.utils.get_logger('worker.%s' % int(time.time() * 100), self.plugin.logger)

        self.hidden_errors = ["Not connected"]

        self.check_connection()

    def sig_timeout_handler(self, signum, frame):
        self.logger.warning('Lost connection to MPD server')
        self.unlock()
        self.terminate()

    def connect(self):
        self.logger.debug('Connecting to MPD server')
        self.lock()
        try:
            signal.alarm(5)
            self.client.connect(self.my_host, self.my_port)
            self.unlock()
            signal.alarm(0)
            self.client.timeout = 5
            self.logger.debug("Successfully connected to MPD daemon.")
            return True
        except mpd.ConnectionError as e:
            if str(e) != "Not connected":
                self.logger.warning("connect encountered mpd.ConnectionError: %s" % (str(e)))
        except mpd.base.ConnectionError as e:
            if str(e) != "Not connected":
                self.logger.warning("connect encountered mpd.base.ConnectionError: %s" % (str(e)))
        except Exception as e:
            if hasattr(e, 'errno'):
                if e.errno == 32:
                    self.logger.warning("connect encountered pipe error")
                elif e.errno == 111:
                    self.logger.warning("connect is unable to connect to MPD daemon.")
                else:
                    self.logger.warning('connect unhandled exception: %s' % e)
            else:
                self.logger.warning('connect unhandled exception, no errno available: %s' % e)

        self.unlock()
        signal.alarm(0)
        return False

    def check_connection(self):
        self.logger.debug('Checking connection to MPD server')
        try:
            self.lock()
            signal.alarm(6)
            self.client.ping()
            signal.alarm(0)
            self.unlock()
            return True
        except mpd.ConnectionError as e:
            if str(e) == "Connection lost while reading line":
                self.logger.debug("check_connection encountered mpd.ConnectionError: %s" % (str(e)))
                self.unlock()
                self.terminate()
            elif str(e) in self.hidden_errors:
                self.logger.debug("check_connection encountered mpd.ConnectionError: %s" % (str(e)))
            else:
                self.logger.info("check_connection encountered mpd.ConnectionError: %s" % (str(e)))
        #                self.client.close()

        except Exception as e:
            self.client.close()
            if hasattr(e, 'errno'):
                if e.errno == 32:
                    self.logger.debug("connect encountered pipe error")
                elif e.errno == 111:
                    self.logger.debug("connect is unable to connect to MPD daemon.")
                else:
                    self.logger.error('connect unhandled exception: %s' % e)
            else:
                self.logger.error('connect unhandled exception, no errno available: %s' % e)

        self.unlock()
        signal.alarm(0)

        if self.connect():
            return True
        else:
            return False

    def lock(self):
        self.worker_lock.acquire()

    def unlock(self):
        if self.worker_lock.locked():
            self.worker_lock.release()

    def play_url(self, uri, volume=-1):
        self.logger.debug('Trying to play URI (%s) with volume (%s)' % (uri, volume))
        if self.check_connection():
            self.lock()
            self.client.command_list_ok_begin()

            if volume >= 0:
                self.client.setvol(volume)

            self.client.clear()

            url_found = False
            try:
                for source in urllib.request.urlopen(uri):
                    if source != "":
                        self.client.add(source.decode('UTF-8').strip().replace('icy://', 'http://'))
                        url_found = True
            except Exception as e:
                self.logger.warning('Unable to open URL (%s): %s' % (uri, e))
                pass

            if url_found:
                self.client.play()

            try:
                self.client.command_list_end()
            except Exception as e:
                self.logger.warning('MPD Warning: %s' % e)

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

    def play_file(self, filename):
        if self.check_connection():
            self.lock()
            try:
                self.client.clear()
                self.client.add(filename)
                self.client.repeat(1)
                self.client.single(1)
                self.client.setvol(0)
                self.client.play()
            except mpd.base.CommandError:
                self.logger.warning("Error starting noise")
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
            self.logger.debug("Stopped")
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
            tmp_status['currentsong'] = self.client.currentsong()
            self.unlock()
            return tmp_status

    def current_song(self):
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

            if 0 <= volume <= 100:
                self.client.setvol(volume)
                self.unlock()
                self.logger.debug("Set volume to %s" % volume)
                return True
        else:
            self.logger.debug('Unable setting volume')
            return False

    def terminate(self):
        self.lock()
        self.plugin.fade_in_progress = False
        self.unlock()
        try:
            self.client.close()
            self.client.disconnect()
        except mpd.ConnectionError:
            self.logger.debug("Could not disconnect because we are not connected.")
        except mpd.base.ConnectionError:
            self.logger.debug("Could not disconnect because we are not connected.")
        self.logger.debug("Disconnected, worker exititing")


class FadeThread(PluginThread):

    def __init__(self, plugin, mpd_client, fade_time, target_vol):
        super(FadeThread, self).__init__(plugin)
        self.mpd_client = mpd_client
        self.fade_time = fade_time
        self.target_vol = target_vol
        self.name = "%s > Created: %s" % (self.name, self.utils.get_time_string())

        # calc fade_time
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
        loop_count = 0
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
            loop_count += 1

            self.mpd_client.lock()
            fade_state = self.plugin.fade_in_progress
            self.mpd_client.unlock()

            if not fade_state:
                return

            if step_count >= step_wait:

                try:
                    self.last_vol = max(1, min(int(self.mpd_client.status()['volume']), 99))
                except Exception:
                    pass

                if increase:
                    self.last_vol += 1
                else:
                    self.last_vol -= 1

                self.mpd_client.setvol(self.last_vol)
                step_count = 0

            if increase:
                if self.last_vol >= self.target_vol:
                    run = False
            else:
                if self.last_vol <= self.target_vol:
                    run = False

            time.sleep(0.1)

    def on_exit(self, result):
        self.plugin.core.add_timeout(0, self.plugin.fade_ended)


class MpdClientPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(MpdClientPlugin, self).__init__(core, descriptor)

        self.myhost = 'localhost'
        self.myport = 6600
        if self.config['nodes'][self.core.hostname]['host']:
            self.myhost = self.config['nodes'][self.core.hostname]['host']
        if self.config['nodes'][self.core.hostname]['port']:
            self.myport = self.config['nodes'][self.core.hostname]['port']
        # self.mypassword = self.config['nodes'][self.core.hostname]['password']

        self.client_worker = MpdClientWorker(self, self.myhost, self.myport)
        self.fade_in_progress = False
        self.thread = None
        self.talkover_volume = self.config['norm_volume']
        self.talkoverActive = False
        self.stations = {}

        volume_command = self.commands.create_subcommand('volume', 'Control the volume', None)
        volume_command.create_subcommand('set', 'Set the volume', self.cmd_volume_set)
        volume_command.create_subcommand('up', 'Increase volume by 5', self.cmd_volume_up)
        volume_command.create_subcommand('down', 'Decrease volume by 5', self.cmd_volume_down)

        self.commands.create_subcommand('noise', 'Start mpd noise mode', self.mpd_noise)

        radio_command = self.commands.create_subcommand('radio', 'Control the web radio', None)
        radio_on_command = radio_command.create_subcommand('on',
                                                           'Turn the radio on [station] default %s ' % self.config[
                                                               'default_st'], self.radio_on)
        radio_command.create_subcommand('off', 'Turn the radio off', self.radio_off)
        radio_command.create_subcommand('toggle', 'Toggles the radio on and off', self.radio_toggle)
        radio_command.create_subcommand('sleep', 'Start mpd sleep mode with station %s' % self.config['sleep_st'],
                                        self.mpd_sleep)
        radio_command.create_subcommand('wakeup', 'Start mpd wakup mode with station %s' % self.config['wakeup_st'],
                                        self.mpd_wakeup)
        radio_command.create_subcommand('list', 'Lists all known stations', self.cmd_list_stations)

        talkover_command = self.commands.create_subcommand('talkover', 'Lowers the volume output', None)
        talkover_command.create_subcommand('on', 'Activate talkover', self.activate_talkover)
        talkover_command.create_subcommand('off', 'Deactivate talkover', self.deactivate_talkover)
        talkover_command.create_subcommand('toggle', 'Toggles talkover', self.toggle_talkover)

        self.radioStarted = 0
        self.wakeups = 0
        self.noises = 0
        self.sleeps = 0
        self.fades = 0
        self.load_state('radioStarted', 0)
        self.load_state('wakeups', 0)
        self.load_state('noises', 0)
        self.load_state('sleeps', 0)
        self.load_state('fades', 0)

        if 'volume_steps' not in self.config.keys():
            self.config['volume_steps'] = 1
        self.config['volume_steps'] = int(self.config['volume_steps'])

        for station in list(self.config['stations'].keys()):
            self.stations[station] = self.config['stations'][station]
            # methodName = 'tuneToStation_' + station
            # def methodName(self):
            #     print "baem"
            #     self.radio_on(self.config['stations'][station])
            radio_on_command.create_subcommand(station, self.config['stations'][station], None)

    def terminate(self):
        self.logger.debug("Terminating MPD client worker")
        self.client_worker.terminate()
        self.logger.debug("Calling wait_for_threads for MPD")
        self.wait_for_threads(self.worker_threads)

    def activate_talkover(self, args):
        self.logger.debug('Activating talkover')
        status = self.client_worker.status()
        if not self.talkoverActive and status['volume'] != self.config['talk_volume']:
            self.talkover_volume = int(status['volume'])
        if self.client_worker.setvol(self.config['talk_volume']):
            self.talkoverActive = True
            return ["Activate talkover"]
        else:
            return ["Unable to connect to MPD"]

    def deactivate_talkover(self, args):
        self.logger.debug('Deactivating talkover')
        if self.client_worker.setvol(self.talkover_volume):
            self.talkoverActive = False
            return ["Deactivate talkover"]
        else:
            return ["Unable to connect to MPD"]

    def toggle_talkover(self, args):
        if self.talkoverActive:
            self.deactivate_talkover(None)
        else:
            self.activate_talkover(None)

    def cmd_list_stations(self, args):
        ret = []
        for station in list(self.stations.keys()):
            ret.append("%-12s %s" % (station, self.stations[station]))
        return ret

    def radio_off(self, args):
        self.logger.debug('Radio off')
        if self.client_worker.stop():
            self.client_worker.clear()
            return ["Radio off"]
        else:
            return ["Unable to connect to MPD"]

    def radio_on(self, args):
        self.client_worker.lock()
        self.fade_in_progress = False
        self.client_worker.unlock()

        station = True
        try:
            self.config['stations'][args[0]]
        except Exception as e:
            station = False
            pass

        if station:
            radio_name = args[0]
            radio_url = self.stations[args[0]]
        else:
            radio_name = self.config['default_st']
            radio_url = self.stations[radio_name]

        if self.client_worker.play_url(radio_url, self.config['norm_volume']):
            self.radioStarted += 1
            self.logger.debug('Radio on %s (%s)' % (radio_name, radio_url))
            return ["Playing station %s" % radio_name]
        else:
            self.logger.debug("Unable to connect to MPD")
            return ["Unable to connect to MPD"]

    def radio_toggle(self, args):
        self.logger.debug('Radio toggle')
        tmp_state = self.client_worker.status()
        self.logger.debug('Current state: %s' % tmp_state)
        if tmp_state:
            if tmp_state['state'] == 'play':
                self.radio_off(args)
            elif tmp_state['state'] == 'paused':
                self.client_worker.play()
            else:
                self.radio_on(args)
            return ["Toggling radio"]
        else:
            return ["Unable to connect to MPD"]

    def cmd_volume_set(self, args):
        self.logger.debug('Set volume to %s' % args[0])
        volume = None
        try:
            volume = int(args[0])
            if 0 <= volume <= 100:
                if self.client_worker.setvol(volume):
                    return ["Volume set to: %s" % volume]
        except Exception:
            pass

        self.logger.debug("Unable to set the volume to: %s" % volume)
        return ["Unable to set the volume to: %s" % volume]

    def cmd_volume_up(self, args):
        self.logger.debug('Increase volume by 5')
        volume = None
        tmp_state = self.client_worker.status()
        try:
            self.logger.debug('Current client volume: %s' % tmp_state['volume'])
            volume = max(0, min(int(tmp_state['volume']) + self.config['volume_steps'], 100))
            self.logger.debug('Try to increase the volume to: %s' % volume)
            if self.client_worker.setvol(volume):
                return ["Volume increased to: %s" % volume]
        except Exception:
            pass

        self.logger.debug("Unable to increase the volume to: %s" % volume)
        return ["Unable to increase the volume to: %s" % volume]

    def cmd_volume_down(self, args):
        self.logger.debug('Decrease volume by 5')
        volume = None
        tmp_state = self.client_worker.status()
        try:
            self.logger.debug('Current client volume: %s' % tmp_state['volume'])
            volume = max(0, min(int(tmp_state['volume']) - self.config['volume_steps'], 100))
            self.logger.debug('Try to decrease the volume to: %s' % volume)
            if self.client_worker.setvol(volume):
                return ["Volume decreased to: %s" % volume]
        except Exception:
            pass

        self.logger.debug("Unable to decrease the volume to: %s" % volume)
        return ["Unable to decrease the volume to: %s" % volume]

    def mpd_sleep(self, args):
        self.sleeps += 1
        self.logger.debug('Activating sleep mode')
        if len(self.core.get_present_users_here()):
            if self.fade_in_progress:
                self.logger.info("MPD Sleep mode NOT activated due other fade in progress")
            else:
                self.radio_off(None)
                self.client_worker.play_url(self.stations[self.config['sleep_st']],
                                            int(self.config['norm_volume']) - self.config['sleep_volume_reduction'])

                self.thread = FadeThread(self,
                                         self.client_worker,
                                         self.config['sleep_fade'],
                                         0)
                self.thread.start()
                self.worker_threads.append(self.thread)
                self.logger.info("MPD Sleep mode activated")
        else:
            self.logger.info("MPD Sleep mode not activated. You are not here.")

    def mpd_noise(self, args):
        self.noises += 1
        self.logger.debug('Activating noise mode')

        if len(self.core.get_present_users_here()):
            if self.fade_in_progress:
                self.logger.info("MPD Noise mode NOT activated due other fade in progress")
                return ["MPD Noise mode NOT activated due other fade in progress"]
            else:
                self.radio_off(None)
                self.client_worker.play_file(self.config['noise_file'])

                self.thread = FadeThread(self,
                                         self.client_worker,
                                         self.config['wakeup_fade'],
                                         self.config['noise_volume'])
                self.thread.start()
                self.worker_threads.append(self.thread)
                self.logger.info("MPD Noise mode activated")
                return ["MPD Noise mode activated"]
        else:
            self.logger.info("Noise not activated. You are not here.")
            return ["Noise not activated. You are not here."]

    def mpd_wakeup(self, args):
        self.wakeups += 1
        tmp_state = self.client_worker.status()
        if tmp_state:
            activate = False

            if 'file' in tmp_state['currentsong'].keys():
                if tmp_state['currentsong']['file'] == self.config['noise_file']:
                    activate = True
                    self.logger.info("Wakeup activating since the noise file is playing.")
            elif tmp_state['state'] != 'play':
                activate = True
            else:
                msg = "Wakeup not activated. Radio is already playing."
                self.logger.info(msg)
                return [msg]

            if activate:
                self.logger.debug('Activating wakeup mode')
                if len(self.core.get_present_users_here()):
                    if self.core.no_alarm_clock:
                        msg = "MPD Wakeup mode NOT activated due no_alarm_clock is set (check gcal)"
                        self.logger.info(msg)
                        return [msg]
                    if self.fade_in_progress:
                        msg = "MPD Wakeup mode NOT activated due other fade in progress"
                        self.logger.info(msg)
                        return [msg]
                    else:
                        self.radio_off(None)
                        self.client_worker.play_url(self.stations[self.config['wakeup_st']], 0)

                        self.thread = FadeThread(self,
                                                 self.client_worker,
                                                 self.config['wakeup_fade'],
                                                 self.config['norm_volume'])
                        self.thread.start()
                        self.worker_threads.append(self.thread)
                        msg = "MPD Wakeup mode activated"
                        self.logger.info(msg)
                        return [msg]
                else:
                    msg = "Wakeup not activated. You are not here."
                    self.logger.info(msg)
                    return [msg]
        else:
            msg = "Wakeup not activated. Unable to connect to MPD."
            self.logger.info(msg)
            return [msg]

    def fade_ended(self):
        self.fades += 1
        self.logger.debug("Fade ending")
        self.client_worker.lock()
        self.fade_in_progress = False
        self.client_worker.unlock()
        if int(self.client_worker.status()['volume']) == 0:
            self.client_worker.stop()
            self.client_worker.clear()
        self.logger.debug("Fade ended")

    # react on presence events
    def process_presence_event(self, presence_before, presence_now):
        if (time.time() - self.core.startup_timestamp) > 10:
            self.logger.debug("MPD Processing presence event")
            if len(presence_now):
                self.logger.debug("Somebody is home. Check to see if a coming_home radio station is configured.")
                if 'coming_home' in self.config['nodes'][self.core.hostname].keys():
                    self.logger.debug("coming_home radio station is %s, starting to play." %
                                      self.config['nodes'][self.core.hostname]['coming_home'])
                    self.core.add_timeout(0, self.radio_on, [self.config['nodes'][self.core.hostname]['coming_home']])
            else:
                self.logger.debug("Nobody is at home. Stopping radio.")
                self.core.add_timeout(0, self.radio_off, False)
        else:
            self.logger.debug("MPD NOT Processing presence event, since only 10 seconds have past since core startup")

    def return_status(self, verbose=False):
        self.logger.debug('Showing status')
        if verbose:
            self.logger.warning("Unlocking mpd client worker")
        self.client_worker.unlock()
        status = self.client_worker.status()
        if verbose:
            self.logger.warning("Requesting status of mpd client worker")
        current_song = self.client_worker.current_song()
        if verbose:
            self.logger.warning("Requesting current song of mpd client worker")

        name = ""
        title = ""
        str_status = "Disconnected"
        volume = ''

        if status:
            str_status = status['state']
            if 'volume' in list(status.keys()):
                volume = status['volume']
            else:
                volume = "-1"

            if 'name' in list(current_song.keys()):
                name = current_song['name']
            if 'title' in list(current_song.keys()):
                title = current_song['title']

            if 'state' in list(status.keys()):
                if status['state'] == "play":
                    str_status = "Playing"
                elif status['state'] == "stop":
                    str_status = "Stopped"
                elif status['state'] == "pause":
                    str_status = "Paused"
            else:
                str_status = "Unknown"

        ret = {'state': str_status, 'title': title, 'name': name, 'volume': volume, 'radioStarted': self.radioStarted,
               'wakeups': self.wakeups, 'noises': self.noises, 'sleeps': self.sleeps, 'fades': self.fades}
        return ret


descriptor = {
    'name': 'mpd-client',
    'help_text': 'Interface to mpd via python-mpc2 lib',
    'command': 'mpd',
    'mode': PluginMode.MANAGED,
    'class': MpdClientPlugin,
    'detailsNames': {'state': "Player status",
                     'title': "Title",
                     'name': "Name",
                     'volume': "Volume",
                     'radioStarted': "Radio started",
                     'wakeups': "Wakeups",
                     'noises': "Noises",
                     'sleeps': "Sleeps",
                     'fades': "Fades"}
}
