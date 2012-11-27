
import subprocess
import sys
from james.plugin import *

#https://github.com/WiringPi/WiringPi-Python

class RaspberryPlugin(Plugin):

	name = 'raspberry'

	def __init__(self, core):
		super(RaspberryPlugin, self).__init__(core, RaspberryPlugin.name)

		#self.create_command('say', self.cmd_say, 'say something')

	def terminate(self):
		pass

	# def cmd_say(self, args):
	# 	self.speak(' '.join(args))

	# def speak(self, msg):
	# 	subprocess.call(['/usr/bin/espeak', msg])



Factory.register_plugin(RaspberryPlugin)


