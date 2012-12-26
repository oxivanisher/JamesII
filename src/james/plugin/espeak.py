
import sys
from time import localtime, strftime, sleep

from james.plugin import *

class EspeakPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(EspeakPlugin, self).__init__(core, descriptor)

        self.core = core
        self.unmuted = self.core.proximity_status.get_status_here()

        self.archived_messages = {}
        self.message_cache = []
        self.talkover = False

        self.commands.create_subcommand('say', 'speak some text via espeak', self.espeak_say)
        self.commands.create_subcommand('archive', 'show the messages in the cache', self.espeak_archive)
        self.speak_hook()

    def espeak_say(self, args):
        text = ' '.join(args)
        if text != '':
            self.speak(text)
            return("Espeak spoke: '%s'" % (text))
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
                           self.name,
                           ('Espeak spoke: %s' % (' '.join(msg))))

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
        if message.level > 0: # we really do not want espeak to speak all debug messages
            if self.unmuted:
                self.speak(message.header)
            else:
                self.archived_messages[message.timestamp] = message.header

    def greet_homecomer(self):
        print("greet homecomer!")
        nicetime = strftime("%H:%M", localtime())

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
        print("processing prox event")
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
