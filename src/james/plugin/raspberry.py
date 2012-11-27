
import subprocess
import sys
from james.plugin import *

#https://github.com/WiringPi/WiringPi-Python

class RaspberryPlugin(Plugin):

	name = 'raspberry'

	def __init__(self, core):
		super(RaspberryPlugin, self).__init__(core, RaspberryPlugin.name)

		self.create_command('rasp_test', self.cmd_rasp_test, 'raspberry test')

	def terminate(self):
		pass

	def cmd_rasp_test(self, args):
		pass




Factory.register_plugin(RaspberryPlugin)


