
import sys
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
        self.unmuted = self.core.proximity_status.get_status_here()
        self.forced_mute = False
        self.espeak_command = self.config['espeak_command'].split()
        self.play_command = self.config['play_command'].split()

        self.archived_messages = []
        self.message_cache = []
        self.talkover = False
        self.load_state('messagesSpoke', 0)

        self.commands.create_subcommand('say', 'Speak some text via espeak (message)', self.espeak_say)
        self.commands.create_subcommand('time', 'Speaks the current time)', self.espeak_time)
        self.commands.create_subcommand('waiting', 'Show the messages in the cache', self.cmd_waiting)
        self.commands.create_subcommand('clear', 'Clears the message in the cache', self.cmd_clear)
        muteCmd = self.commands.create_subcommand('muteswitch', 'Toggles muting of all output', self.cmd_mute)
        muteCmd = self.commands.create_subcommand('mute', 'Toggles muting of all output', False)
        muteCmd.create_subcommand('on', 'Force activating mute', self.cmd_mute_on)
        muteCmd.create_subcommand('off', 'Force deactivating mute', self.cmd_mute_off)
        self.commands.create_subcommand('mutestate', 'Shows the current muted state', self.cmd_mutestate)

        atexit.register(self.save_archived_messages)
        self.load_archived_messages()

        atexit.register(self.save_muted_state)
        self.load_muted_state()

        self.speak_lock = threading.Lock()

    def start(self):
        # wait 1 seconds befor working
        self.core.add_timeout(1, self.speak_hook)

    def load_archived_messages(self):
        try:
            file = open(self.message_archive_file, 'r')
            # self.archived_messages = self.utils.convert_from_unicode(json.loads(file.read()))
            self.archived_messages = json.loads(file.read())
            file.close()

        except IOError:
            pass
        pass

    def save_archived_messages(self):
        try:
            file = open(self.message_archive_file, 'w')
            file.write(json.dumps(self.archived_messages))
            file.close()
            self.logger.debug("Saving archived messages to %s" % (self.message_archive_file))
        except IOError:
            self.logger.warning("Could not safe archived messages to file!")

    def load_muted_state(self):
        try:
            file = open(self.mute_file, 'r')
            self.forced_mute = json.loads(file.read())
            file.close()

        except IOError:
            pass
        pass

    def save_muted_state(self):
        try:
            file = open(self.mute_file, 'w')
            file.write(json.dumps(self.forced_mute))
            file.close()
            self.logger.debug("Saving muted state to %s" % (self.mute_file))
        except IOError:
            self.logger.warning("Could not safe muted state to file!")

    def espeak_say(self, args):
        text = ' '.join(args)
        if text != '':
            self.speak(text + '.')
            return ["Espeak will speak: '%s'" % (text)]
        return "No text entered for espeak"

    def alert(self, args):
        self.logger.debug('Alerting (%s)' % ' '.join(args))

        adminIsHere = False
        for person in self.core.persons_status:
            if self.core.persons_status[person]:
                try:
                    if self.core.config['persons'][person]['admin']:
                        adminIsHere = True
                except Exception:
                    pass

        if self.unmuted and adminIsHere and self.core.proximity_status.get_status_here():
            self.espeak_say(args)
            if len(self.archived_messages):
                self.greet_homecomer()
        else:
            self.logger.debug("Added message: %s to archive" % ' '.join(args))
            self.archived_messages.append((time.time(), ' '.join(args)))

    def espeak_time(self, args):
        self.speak('It is now %s' % self.utils.get_time_string())
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
            muteMessage = "Forced mute disabled"
        else:
            self.forced_mute = True
            muteMessage = "Forced mute enabled"
        self.logger.info(muteMessage)
        return [muteMessage]

    def cmd_mutestate(self, args):
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
            self.utils.popenAndWait(self.espeak_command + ['-w', tempFile.name] + [msg])
            self.utils.popenAndWait(self.play_command + [tempFile.name])
            os.remove(tempFile.name)
            self.logger.debug('Espeak spoke: %s' % (msg.rstrip()))
        else:
            self.logger.info('Espeak did not speak (muted): %s' % (msg.rstrip()))

    def speak_hook(self, args = None):
        if len(self.message_cache) > 0:
            self.messagesSpoke += len(self.message_cache)
            self.speak_lock.acquire()
            msg = ''
            for message in self.message_cache:
                try:
                    end = message[-1]
                    if end != "." and end != ":" and end != "!" and end != "?":
                        message += "."
                    msg += message + "\n"
                except IndexError:
                    pass
            self.message_cache = []
            self.talkover = True
            try:
                self.core.commands.process_args(['mpd', 'talkover', 'on'])
            except Exception:
                pass
            self.speak_lock.release()
            self.logger.info('Espeak will say: %s' % msg.rstrip())
            self.worker_threads.append(self.core.spawnSubprocess(self.speak_worker, self.speak_hook, msg, self.logger))
        else:
            if self.talkover:
                self.talkover = False
                try:
                    self.core.commands.process_args(['mpd', 'talkover', 'off'])
                except Exception:
                    pass
            self.core.add_timeout(1, self.speak_hook)

        return

    def process_message(self, message):
        self.unmuted = self.core.proximity_status.get_status_here()
        if message.level > 0: # we really do not want espeak to speak all debug messages
            if self.unmuted:
                self.speak(message.header)
            else:
                self.archived_messages.append((time.time(), message.header))

    def greet_homecomer(self):
        self.speak_lock.acquire()

        isHere = []
        adminIsHere = False
        for person in self.core.persons_status:
            if self.core.persons_status[person]:
                isHere.append(person)
                try:
                    if self.core.config['persons'][person]['admin']:
                        adminIsHere = True
                except Exception:
                    pass

        nicetime = time.strftime("%H:%M", time.localtime())

        if (time.time() - self.core.startup_timestamp) > 10:
            if len(isHere):
                self.message_cache.append('Hey ' + ' and '.join(isHere) + ' it is now %s' % self.utils.get_time_string())

        if adminIsHere:
            if len(self.archived_messages) > 0:
            # reading the log to the admin
                if len(self.archived_messages) == 1:
                    self.message_cache.append('While we where apart, the following thing happend:')
                else:
                    self.message_cache.append('While we where apart, the following %s things happend:' % len(self.archived_messages))
                work_archived_messages = self.archived_messages
                self.archived_messages = []
                for (timestamp, message) in work_archived_messages:
                    self.message_cache.append(self.utils.get_nice_age(int(timestamp)) + ", " + message)

                self.message_cache.append("End of Log")
                
            else:
                self.message_cache.append('Nothing happend while we where apart.')

        self.speak_lock.release()

    def process_proximity_event(self, newstatus):
        self.logger.debug("Espeak Processing proximity event")
        self.unmuted = newstatus['status'][self.core.location]
        if newstatus['status'][self.core.location]:
            self.core.add_timeout(0, self.greet_homecomer)

    def terminate(self):
        self.wait_for_threads(self.worker_threads)

    def return_status(self, verbose = False):
        ret = {}
        ret['archivedMessage'] = len(self.archived_messages)
        ret['messagesCache'] = len(self.message_cache)
        ret['talkoverActive'] = self.talkover
        ret['messagesSpoke'] = self.messagesSpoke
        return ret

descriptor = {
    'name' : 'espeak',
    'help' : 'Interface to espeak',
    'command' : 'espeak',
    'mode' : PluginMode.MANAGED,
    'class' : EspeakPlugin,
    'detailsNames' : { 'archivedMessage' : "Archived messages",
                       'messagesCache' : "Currently cached messages",
                       'messagesSpoke' : "Messages spoken",
                       'talkoverActive' : "Talkover currently active"}
}
