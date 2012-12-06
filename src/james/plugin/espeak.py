
import subprocess
import sys

from james.plugin import *

class EspeakPlugin(Plugin):

	def __init__(self, core):
		super(EspeakPlugin, self).__init__(core, EspeakPlugin.name)

		self.create_command('say', self.cmd_say, 'say something')

	def terminate(self):
		pass

	def cmd_say(self, args):
		self.speak(' '.join(args))

	def speak(self, msg):
		subprocess.call(['/usr/bin/espeak', msg])


descriptor = {
	'name' : 'espeak',
	'mode' : PluginMode.MANAGED,
	'class' : EspeakPlugin
}
