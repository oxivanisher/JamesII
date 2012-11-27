
import subprocess
import sys
import wiringpi
#https://github.com/WiringPi/WiringPi-Python

from james.plugin import *


class RaspberryPlugin(Plugin):

	name = 'raspberry'

	def __init__(self, core):
		super(RaspberryPlugin, self).__init__(core, RaspberryPlugin.name)

		self.create_command('rasp_test', self.cmd_rasp_test, 'raspberry test')

		io = wiringpi.GPIO(wiringpi.GPIO.WPI_MODE_PINS)
		
		#io.pinMode(1,io.OUTPUT)
		#io.digitalWrite(1,io.HIGH)


	def terminate(self):
		pass

	def cmd_rasp_test(self, args):
		io.pinMode(1,io.OUTPUT)
		io.digitalWrite(1,io.HIGH)
		pass




Factory.register_plugin(RaspberryPlugin)


