
import subprocess
import sys
from time import localtime, strftime

from james.plugin import *

class EspeakPlugin(Plugin):

    def __init__(self, core):
        super(EspeakPlugin, self).__init__(core, EspeakPlugin.name)

        self.core = core
        self.unmuted = self.core.proximity_status.get_status_here()

        self.create_command('espeak_say', self.cmd_say, 'say something')
        self.create_command('espeak_showarchive', self.cmd_showarchive, 'shows the message archive')
        self.archived = {}

    def terminate(self):
        pass

    def cmd_say(self, args):
        self.speak(' '.join(args))

    def cmd_showarchive(self, args):
        ret = ""
        if len(self.archived):
        # reading the log
            for timestamp in self.archived.keys():
                ret += ("%-20s %s\n" % (self.core.utils.get_nice_age(int(timestamp)), self.archived[timestamp]))
        else:
            ret = "No Messages waiting"

        return ret

    def speak(self, msg):
        with open(os.devnull, "w") as fnull:
            ret = subprocess.Popen(['/usr/bin/espeak', msg], \
                  stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]

            message = self.core.new_message(self.name)
            message.header = "Espeak Spoke"
            message.body = msg
            message.send()


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
        else:
            self.speak('Nothing happend while we where apart.')

    def process_proximity_event(self, newstatus):
        self.unmuted = newstatus['status'][self.core.location]
        if newstatus['status'][self.core.location]:
            self.greet_homecomer()

descriptor = {
    'name' : 'espeak',
    'mode' : PluginMode.MANAGED,
    'class' : EspeakPlugin
}
