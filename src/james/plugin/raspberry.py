
import subprocess
import sys


wiringpi_found = True
try:
	import wiringpi
except ImportError, e:
	wiringpi_found = False
#https://github.com/WiringPi/WiringPi-Python

from james.plugin import *


class RaspberryPlugin(Plugin):

	name = 'raspberry'

	def __init__(self, core):

		super(RaspberryPlugin, self).__init__(core, RaspberryPlugin.name)


		if wiringpi_found:
			self.create_command('rasp_test', self.cmd_rasp_test, 'raspberry test')
			self.gpio = wiringpi.GPIO(wiringpi.GPIO.WPI_MODE_PINS)
		
		#gpio.pinMode(1,gpio.OUTPUT)
		#gpio.digitalWrite(1,gpio.HIGH)


	def terminate(self):
		pass

	def cmd_rasp_test(self, args):
		self.gpio.pinMode(1,self.gpio.OUTPUT)
		self.gpio.digitalWrite(1,self.gpio.HIGH)
		pass




Factory.register_plugin(RaspberryPlugin)


