
import subprocess
import sys
from time import localtime, strftime

from james.plugin import *

class EspeakPlugin(Plugin):

    def __init__(self, core):
        super(EspeakPlugin, self).__init__(core, EspeakPlugin.name)

        self.core = core
        self.unmuted = self.core.proximity_status.get_status_here()

        self.create_command('espeak', self.cmd_espeak, 'espeak api')

        self.archived_messages = {}

    def cmd_espeak(self, args):
        sub_commands = {'say' : self.espeak_say,
                        'archive' : self.espeak_archive}

        output = ("subcommands are: %s" % (', '.join(sub_commands.keys())))
        try:
            user_command = args[0]
        except Exception as e:
            return (output)
        for command in sub_commands.keys():
            if command == user_command:
                return sub_commands[command](args[1:])
        return (output)

    def espeak_say(self, args):
        text = ' '.join(args)
        if text != '':
            self.speak(text)
            return("spoke: '%s'" % (text))
        return "no text entered"

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
        with open(os.devnull, "w") as fnull:
            ret = subprocess.Popen(['/usr/bin/espeak', msg], \
                  stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]

            message = self.core.new_message(self.name)
            message.header = "Espeak Spoke"
            message.body = msg
            message.send()

    def process_message(self, message):
        if message.level > 0: # we really do not want espeak to speak all debug messages
            if self.unmuted:
                self.speak(message.header)
            else:
                self.archived_messages[message.timestamp] = message.header

    def greet_homecomer(self):
        nicetime = strftime("%H:%M", localtime())

        self.speak('Welcome home. It is now %s.' % (nicetime))

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
        self.unmuted = newstatus['status'][self.core.location]
        if newstatus['status'][self.core.location]:
            self.greet_homecomer()

descriptor = {
    'name' : 'espeak',
    'mode' : PluginMode.MANAGED,
    'class' : EspeakPlugin
}
