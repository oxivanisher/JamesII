
import sys
import atexit
import json
import time

from james.plugin import *

class EspeakPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(EspeakPlugin, self).__init__(core, descriptor)

        self.core = core
        self.message_archive_file = os.path.join(os.path.expanduser("~"), ".james_message_archive")
        self.unmuted = self.core.proximity_status.get_status_here()
        self.espeak_command = self.core.config['espeak']['espeak_command'].split()

        self.archived_messages = []
        self.message_cache = []
        self.talkover = False

        self.commands.create_subcommand('say', 'Speak some text via espeak (message)', self.espeak_say)
        self.commands.create_subcommand('waiting', 'Show the messages in the cache', self.cmd_waiting)
        atexit.register(self.save_archived_messages)
        self.load_archived_messages()

    def start(self):
        # wait 1 seconds befor working
        self.core.add_timeout(1, self.speak_hook)

    def load_archived_messages(self):
        try:
            file = open(self.message_archive_file, 'r')
            # self.archived_messages = self.core.utils.convert_from_unicode(json.loads(file.read()))
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

    def espeak_say(self, args):
        text = ' '.join(args)
        if text != '':
            self.speak(text)
            return(["Espeak will speak: '%s'" % (text)])
        return "No text entered for espeak"

    def cmd_waiting(self, args):
        # listing waiting messages
        ret = []
        for (timestamp, message) in self.archived_messages:
            ret.append("%-20s %s" % (self.core.utils.get_nice_age(int(timestamp)),
                                     message))
        if not ret:
            ret.append("no messages waiting")
        return ret

    def speak(self, msg):
        self.message_cache.append(msg)

    def speak_worker(self, msg):
        #FIXME: THIS IS A VERRRRRRRY DIRTY RASPBERRY WORKAROUND!
        self.core.utils.popenAndWait(self.espeak_command + [msg] + ['|', 'aplay', '-D', 'plug:hw:0'])
        self.logger.info('Espeak spoke: %s' % (msg))

    def speak_hook(self, args = None):
        if len(self.message_cache) > 0:
            msg = '\n'.join(self.message_cache)
            self.message_cache = []
            # msg = self.message_cache[0]
            # self.message_cache.pop(0)
            self.talkover = True
            try:
                self.core.commands.process_args(['mpd', 'talkover', 'on'])
            except Exception:
                pass
            self.logger.debug('Espeak will say: %s' % msg)
            self.core.spawnSubprocess(self.speak_worker, self.speak_hook, msg)
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
        nicetime = time.strftime("%H:%M", time.localtime())

        if (time.time() - self.core.startup_timestamp) > 10:
            self.speak('Welcome. It is now %s.' % (nicetime))

        if len(self.archived_messages) > 0:
        # reading the log
            speak_text = 'While we where apart, the following things happend:'
            work_archived_messages = self.archived_messages
            self.archived_messages = []
            for (timestamp, message) in work_archived_messages:
                speak_text += "\n" + self.core.utils.get_nice_age(int(timestamp)) + ", " + message + "."

            speak_text += "\nEnd of Log"

            self.speak(speak_text)
            
        else:
            self.speak('Nothing happend while we where apart.')

    def process_proximity_event(self, newstatus):
        self.logger.debug("Espeak Processing proximity event")
        self.unmuted = newstatus['status'][self.core.location]
        if newstatus['status'][self.core.location]:
            self.greet_homecomer()

descriptor = {
    'name' : 'espeak',
    'help' : 'Interface to espeak',
    'command' : 'espeak',
    'mode' : PluginMode.MANAGED,
    'class' : EspeakPlugin
}
