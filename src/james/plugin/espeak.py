
import sys
import atexit
import json
from time import localtime, strftime, sleep, time

from james.plugin import *

class EspeakPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(EspeakPlugin, self).__init__(core, descriptor)

        self.core = core
        self.message_archive_file = os.path.join(os.path.expanduser("~"), ".james_message_archive")
        self.unmuted = self.core.proximity_status.get_status_here()

        self.archived_messages = {}
        self.message_cache = []
        self.talkover = False

        self.commands.create_subcommand('say', 'speak some text via espeak', self.espeak_say)
        self.commands.create_subcommand('archive', 'show the messages in the cache', self.espeak_archive)
        atexit.register(self.save_archived_messages)
        self.load_archived_messages()
        self.speak_hook()

    def load_archived_messages(self):
        try:
            file = open(self.message_archive_file, 'r')
            self.archived_messages = self.core.utils.convert_from_unicode(json.loads(file.read()))
            file.close()

        except IOError:
            pass
        pass

    def save_archived_messages(self):
        try:
            file = open(self.message_archive_file, 'w')
            file.write(json.dumps(self.archived_messages))
            file.close()
            if self.core.config['core']['debug']:
                print("Saving archived messages to %s" % (self.message_archive_file))
        except IOError:
            print("WARNING: Could not safe archived messages to file!")

    def espeak_say(self, args):
        text = ' '.join(args)
        if text != '':
            self.speak(text)
            return(["Espeak will speak: '%s'" % (text)])
        return "No text entered for espeak"

    def espeak_archive(self, args):
        ret = []
        if len(self.archived_messages):
        # reading the log
            for timestamp in self.archived_messages.keys():
                ret.append("%-20s %s" % (self.core.utils.get_nice_age(int(timestamp)),
                                           self.archived_messages[timestamp]))
        else:
            ret.append("no messages waiting")

        return ret

    def speak(self, msg):
        self.message_cache.append(msg)

    def speak_worker(self, msg):
        self.core.utils.popenAndWait(['/usr/bin/espeak', msg])
        self.send_response(self.uuid,
                           'broadcast',
                           (['Espeak spoke: %s' % (msg)]))

    def speak_hook(self, args = None):
        if len(self.message_cache) > 0:
            msg = self.message_cache[0]
            try:
                self.message_cache = self.message_cache[1:]
            except Exception as e:
                self.message_cache = []
                pass

            self.talkover = True
            try:
                self.core.commands.process_args(['mpd', 'talkover', 'on'])
            except Exception:
                pass
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
                self.archived_messages[int(message.timestamp)] = message.header

    def greet_homecomer(self):
        nicetime = strftime("%H:%M", localtime())

        if (time() - self.core.startup_timestamp) > 10:
            self.speak('Welcome. It is now %s.' % (nicetime))

        if len(self.archived_messages):
        # reading the log
            self.speak('While we where apart, the following things happend:')
            for timestamp in self.archived_messages.keys():
                self.speak(self.core.utils.get_nice_age(int(timestamp)) + ": " + self.archived_messages[timestamp])
            self.archived_messages = {}
            self.speak('End of Log')
        else:
            self.speak('Nothing happend while we where apart.')

    def process_proximity_event(self, newstatus):
        if self.core.config['core']['debug']:
            print("Espeak Processing proximity event")
        self.unmuted = newstatus['status'][self.core.location]
        if newstatus['status'][self.core.location]:
            self.greet_homecomer()

descriptor = {
    'name' : 'espeak',
    'help' : 'espeak api',
    'command' : 'espeak',
    'mode' : PluginMode.MANAGED,
    'class' : EspeakPlugin
}
