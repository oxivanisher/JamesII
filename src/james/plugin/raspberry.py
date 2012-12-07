
import subprocess
import sys
import wiringpi

#https://github.com/WiringPi/WiringPi-Python

from james.plugin import *


class RaspberryPlugin(Plugin):

    def __init__(self, core):

        super(RaspberryPlugin, self).__init__(core, RaspberryPlugin.name)

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



descriptor = {
    'name' : 'raspberry',
    'mode' : PluginMode.MANAGED,
    'class' : RaspberryPlugin
}

