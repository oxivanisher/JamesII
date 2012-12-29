
import subprocess
import sys
import wiringpi

#https://github.com/WiringPi/WiringPi-Python

from james.plugin import *

# FIXME!
# class RasperryThread(Thread):
#     pass

#     def run(self):
#         while True:
#             # read pin
#             pass



class RaspberryPlugin(Plugin):

    def __init__(self, core, descriptor):

        super(RaspberryPlugin, self).__init__(core, descriptor)

        self.gpio = wiringpi.GPIO(wiringpi.GPIO.WPI_MODE_PINS)
        
        #gpio.pinMode(1,gpio.OUTPUT)
        #gpio.digitalWrite(1,gpio.HIGH)

        if core.os_username == 'root':
            self.commands.create_subcommand('test', 'Test command for raspberry. turns on the 2nd led', self.rasp_test)

    def rasp_test(self, args):
        self.gpio.pinMode(1,self.gpio.OUTPUT)
        self.gpio.digitalWrite(1,self.gpio.HIGH)

        message = self.core.new_message(self.name)
        message.header = "Testing RaspberryPi"
        message.send()

descriptor = {
    'name' : 'raspberry',
    'help' : 'Interface to RaspberryPi',
    'command' : 'rasp',
    'mode' : PluginMode.MANAGED,
    'class' : RaspberryPlugin
}

