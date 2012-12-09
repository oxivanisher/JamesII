
import subprocess
import sys
import wiringpi

#https://github.com/WiringPi/WiringPi-Python

from james.plugin import *


class RaspberryPlugin(Plugin):

    def __init__(self, core):

        super(RaspberryPlugin, self).__init__(core, RaspberryPlugin.name)

        self.create_command('rasp', self.cmd_rasp, 'raspberry api')

        self.gpio = wiringpi.GPIO(wiringpi.GPIO.WPI_MODE_PINS)
        
        #gpio.pinMode(1,gpio.OUTPUT)
        #gpio.digitalWrite(1,gpio.HIGH)


    def cmd_rasp(self, args):
        sub_commands = {'test' : self.rasp_test}

        output = ("subcommands are: %s" % (', '.join(sub_commands.keys())))
        try:
            user_command = args[0]
        except Exception as e:
            return (output)
        for command in sub_commands.keys():
            if command == user_command:
                return sub_commands[command](args[1:])
        return (output)

    def rasp_test(self, args):
        self.gpio.pinMode(1,self.gpio.OUTPUT)
        self.gpio.digitalWrite(1,self.gpio.HIGH)

        message = self.core.new_message(self.name)
        message.header = "Testing RaspberryPi"
        message.send()
        
        pass

descriptor = {
    'name' : 'raspberry',
    'mode' : PluginMode.MANAGED,
    'class' : RaspberryPlugin
}

