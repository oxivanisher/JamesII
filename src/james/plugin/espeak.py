
import subprocess
import sys
from time import localtime, strftime

from james.plugin import *

class EspeakPlugin(Plugin):

    def __init__(self, core):
        super(EspeakPlugin, self).__init__(core, EspeakPlugin.name)

        self.core = core
        self.unmuted = self.core.proximity_status.get_status_here()

        self.create_command('say', self.cmd_say, 'say something')
        self.archived = {}

    def terminate(self):
        pass

    def cmd_say(self, args):
        self.speak(' '.join(args))

    def speak(self, msg):
        subprocess.call(['/usr/bin/espeak', msg])

    def process_message(self, message):
        if message.level > 0:
            if self.unmuted:
                print("Espeak is speaking a message from %s@%s:\n%s:%s" % (message.sender_name,
                                                                        message.sender_host,
                                                                        message.header,
                                                                        message.body))
                self.speak(message.header)
            else:
                self.archived[message.timestamp] = message.header

    def greet_homecomer(self):
        nicetime = strftime("%H:%M", localtime())

        self.speak('Welcome home. It is now %s.' % (nicetime))

        if len(self.archived):
        # reading the log
            self.speak('While we where apart, the following things happend:')
            for timestamp in self.archived.keys():
                self.speak(self.core.utils.get_nice_age(int(timestamp)) + ": " + self.archived[timestamp])
            self.archived = {}
            self.speak('End of Log')

    def process_proximity_event(self, newstatus):
        self.unmuted = newstatus
        if newstatus:
            self.greet_homecomer()

descriptor = {
    'name' : 'espeak',
    'mode' : PluginMode.MANAGED,
    'class' : EspeakPlugin
}
