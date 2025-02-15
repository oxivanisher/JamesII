import atexit
import json
import time
import threading
import tempfile
import os

from james.plugin import *


class EspeakPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(EspeakPlugin, self).__init__(core, descriptor)

        self.message_archive_file = os.path.join(os.path.expanduser("~"), ".james_espeak_message_archive")
        self.mute_file = os.path.join(os.path.expanduser("~"), ".james_muted")
        self.unmuted = True
        self.forced_mute = False
        self.espeak_command = self.config['espeak_command'].split()
        self.play_command = self.config['play_command'].split()

        self.archived_messages = []
        self.message_cache = []
        self.messagesSpoke = 0
        self.talkover = False
        self.talking_finished = False
        self.load_state('messagesSpoke', 0)
        self.last_spoken = 0
        self.speaker_waking_up_until = 0
        self.speaker_wakeup_sent = False
        self.speaker_sleep_timeout = 0
        self.speaker_wakeup_duration = 0

        try:
            if 'speaker_sleep_timeout' in self.config['nodes'][self.core.hostname].keys():
                self.speaker_sleep_timeout = int(self.config['nodes'][self.core.hostname]['speaker_sleep_timeout'])
            if 'speaker_wakeup_duration' in self.config['nodes'][self.core.hostname].keys():
                self.speaker_wakeup_duration = int(self.config['nodes'][self.core.hostname]['speaker_wakeup_duration'])
            self.logger.debug(
                f"Espeak will handle sleeping speakers, {self.speaker_sleep_timeout}/{self.speaker_wakeup_duration}")
        except TypeError as e:
            self.logger.warning("The configuration changed for espeak. Please check the example configuration.")

        self.commands.create_subcommand('say', 'Speak some text via espeak (msg)', self.espeak_say)
        self.commands.create_subcommand('time', 'Speaks the current time)', self.espeak_time)
        self.commands.create_subcommand('waiting', 'Show the messages in the cache', self.cmd_waiting)
        self.commands.create_subcommand('clear', 'Clears the msg in the cache', self.cmd_clear)
        mute_cmd = self.commands.create_subcommand('muteswitch', 'Toggles muting of all output', self.cmd_mute)
        mute_cmd = self.commands.create_subcommand('mute', 'Toggles muting of all output', False)
        mute_cmd.create_subcommand('on', 'Force activating mute', self.cmd_mute_on)
        mute_cmd.create_subcommand('off', 'Force deactivating mute', self.cmd_mute_off)
        self.commands.create_subcommand('mutestate', 'Shows the current muted state', self.cmd_mute_state)

        atexit.register(self.save_archived_messages)
        self.load_archived_messages()

        atexit.register(self.save_muted_state)
        self.load_muted_state()

        self.speak_lock = threading.Lock()

    def start(self):
        # wait 1 second before working
        self.core.add_timeout(1, self.speak_hook)

    def load_archived_messages(self):
        try:
            file = open(self.message_archive_file, 'r')
            # self.archived_messages = self.utils.convert_from_unicode(json.loads(file.read()))
            self.archived_messages = json.loads(file.read())
            file.close()
        except IOError:
            pass

    def save_archived_messages(self):
        try:
            file = open(self.message_archive_file, 'w')
            file.write(json.dumps(self.archived_messages))
            file.close()
            self.logger.debug(f"Saving archived messages to {self.message_archive_file}")
        except IOError:
            self.logger.warning("Could not save archived messages to file!")

    def load_muted_state(self):
        try:
            file = open(self.mute_file, 'r')
            self.forced_mute = json.loads(file.read())
            file.close()
        except IOError:
            pass

    def save_muted_state(self):
        try:
            file = open(self.mute_file, 'w')
            file.write(json.dumps(self.forced_mute))
            file.close()
            self.logger.debug(f"Saving muted state to {self.mute_file}")
        except IOError:
            self.logger.warning("Could not save muted state to file!")

    def espeak_say(self, args):
        text = ' '.join(args)
        if text != '':
            self.speak(text + '.')
            return [f"Espeak will speak: '{text}'"]
        return "No text entered for espeak"

    def alert(self, args):
        self.logger.debug(f"Alerting ({' '.join(args)})")
        if self.check_unmuted() and self.core.is_admin_user_here() and len(self.core.get_present_users_here()):
            self.espeak_say(args)
            if len(self.archived_messages):
                self.greet_homecomer()
        else:
            self.logger.debug(f"Added msg: {' '.join(args)} to archive")
            self.archived_messages.append((time.time(), ' '.join(args)))

    def espeak_time(self, args):
        self.speak(f'It is now {self.utils.get_time_string()}')
        return "Espeak will speak the time"

    def cmd_waiting(self, args):
        # listing waiting messages
        ret = []
        for (timestamp, message) in self.archived_messages:
            ret.append("%-20s %s" % (self.utils.get_nice_age(int(timestamp)),
                                     message))
        if not ret:
            ret.append("no messages waiting")
        return ret

    def cmd_clear(self, args):
        # clear waiting messages
        ret = []
        for (timestamp, message) in self.archived_messages:
            ret.append("%-20s %s" % (self.utils.get_nice_age(int(timestamp)),
                                     message))

        if not ret:
            ret.append("No messages waiting")
        else:
            self.archived_messages = []
            ret.append("Clearing the following messages:")

        return ret

    def cmd_mute_on(self, args):
        self.forced_mute = True
        return ["Forced mute enabled"]

    def cmd_mute_off(self, args):
        self.forced_mute = False
        return ["Forced mute disabled"]

    def cmd_mute(self, args):
        if self.forced_mute:
            self.forced_mute = False
            mute_message = "Forced mute disabled"
        else:
            self.forced_mute = True
            mute_message = "Forced mute enabled"
        self.logger.info(mute_message)
        return [mute_message]

    def cmd_mute_state(self, args):
        if self.forced_mute:
            return ["Forced mute enabled"]
        else:
            return ["Forced mute disabled"]

    def speak(self, msg):
        self.speak_lock.acquire()
        self.message_cache.append(msg)
        self.speak_lock.release()

    def speak_worker(self, msg):
        if not self.forced_mute:
            tempFile = tempfile.NamedTemporaryFile(suffix="-JamesII-Espeak", delete=False)

            espeak_command = self.espeak_command + ['-w', tempFile.name] + [msg]
            self.logger.debug(f"Espeak command: {' '.join(espeak_command)}")

            aplay_command = self.play_command + [tempFile.name]
            self.logger.debug(f"Aplay command: {' '.join(aplay_command)}")

            with self.speak_lock:
                self.talking_finished = False

            time.sleep(1) # give mpd a little bit time to enable talkover

            self.utils.popen_and_wait(espeak_command)
            self.utils.popen_and_wait(aplay_command)
            os.remove(tempFile.name)

            self.logger.debug(f'Espeak spoke: {msg.rstrip()}')
            with self.speak_lock:
                self.talking_finished = True
        else:
            self.logger.info(f'Espeak did not speak (muted): {msg.rstrip()}')

    def speak_hook(self, args=None):
        current_time = time.time()

        if self.message_cache:
            if self.speaker_sleep_timeout and self.speaker_wakeup_duration:
                if self.last_spoken + self.speaker_sleep_timeout > current_time:
                    # Speakers are still awake
                    with self.speak_lock:
                        self.speaker_wakeup_sent = False
                elif not self.speaker_wakeup_sent:
                    # Need to wake up speakers
                    self.logger.info(
                        f'Waking up speakers, waiting {self.speaker_wakeup_duration} seconds before speaking...'
                    )
                    self.speaker_waking_up_until = current_time + self.speaker_wakeup_duration
                    self.worker_threads.append(
                        self.core.spawn_subprocess(
                            self.speak_worker, self.speak_hook, "i", self.logger
                        )
                    )
                    with self.speak_lock:
                        self.speaker_wakeup_sent = True

                    # Delay speaking until speakers are awake
                    self.core.add_timeout(self.speaker_wakeup_duration, self.speak_hook)
                    return

            # Ensure wake-up period has passed before speaking
            if self.speaker_waking_up_until > current_time:
                self.logger.debug(
                    f'Waiting for speakers to wake up ({round(self.speaker_waking_up_until - current_time, 2)}s left)...')
                self.core.add_timeout(1, self.speak_hook)
                return

            # Proceed to speaking
            self.messagesSpoke += len(self.message_cache)
            with self.speak_lock:
                msg = ''
                for message in self.message_cache:
                    if message and message[-1] not in ".:!?":
                        message += "."
                    msg += message + "\n"
                self.message_cache.clear()

            with self.speak_lock:
                self.talkover = True
            try:
                self.logger.debug('Enabling talkover')
                self.core.commands.process_args(['mpd', 'talkover', 'on'])
            except Exception:
                pass

            self.logger.info(f'Espeak will say: {msg.rstrip()}')
            self.last_spoken = time.time()
            self.worker_threads.append(self.core.spawn_subprocess(self.speak_worker, self.speak_hook, msg, self.logger))

        else:
            # Ensure talkover is disabled when nothing is being spoken
            with self.speak_lock:
                if self.talking_finished and self.talkover:
                    self.talkover = False
                    self.talking_finished = False
                    self.logger.debug('Disabling talkover')
                    self.core.commands.process_args(['mpd', 'talkover', 'off'])

            # Periodically check for new messages
            self.core.add_timeout(1, self.speak_hook)

    def process_message(self, message):
        if message.level > 0:  # we really do not want espeak to speak all debug messages
            if self.check_unmuted():
                self.speak(message.header)
            else:
                self.archived_messages.append((time.time(), message.header))

    def greet_homecomer(self):
        with self.speak_lock:
            if (time.time() - self.core.startup_timestamp) > 10:
                if len(self.core.get_present_users_here()):
                    self.message_cache.append(
                        f'Hey ' + ' and '.join(
                            self.core.get_present_users_here()) + ' it is now {self.utils.get_time_string()')

            if self.core.is_admin_user_here():
                if len(self.archived_messages) > 0:
                    # reading the log to the admin
                    if len(self.archived_messages) == 1:
                        self.message_cache.append('While we where apart, the following thing happened:')
                    else:
                        self.message_cache.append(
                            f'While we where apart, the following {len(self.archived_messages)} things happened:')
                    work_archived_messages = self.archived_messages
                    self.archived_messages = []
                    for (timestamp, message) in work_archived_messages:
                        self.message_cache.append(self.utils.get_nice_age(int(timestamp)) + ", " + message)

                    self.message_cache.append("End of Log")

                else:
                    self.message_cache.append('Nothing happened while we where apart.')

    def process_presence_event(self, presence_before, presence_now):
        self.logger.debug("Espeak Processing presence event")
        self.check_unmuted()
        if len(presence_now):
            self.core.add_timeout(0, self.greet_homecomer)

    def check_unmuted(self):
        if len(self.core.get_present_users_here()):
            self.unmuted = True
        else:
            self.unmuted = False
        return self.unmuted

    def terminate(self):
        self.wait_for_threads(self.worker_threads)

    def return_status(self, verbose=False):
        ret = {'archivedMessage': len(self.archived_messages), 'messagesCache': len(self.message_cache),
               'talkoverActive': self.talkover, 'messagesSpoke': self.messagesSpoke}
        return ret


descriptor = {
    'name': 'espeak',
    'help_text': 'Interface to espeak',
    'command': 'espeak',
    'mode': PluginMode.MANAGED,
    'class': EspeakPlugin,
    'detailsNames': {'archivedMessage': "Archived messages",
                     'messagesCache': "Currently cached messages",
                     'messagesSpoke': "Messages spoken",
                     'talkoverActive': "Talkover currently active"}
}
