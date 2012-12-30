
import subprocess
import sys
import wiringpi

#https://github.com/WiringPi/WiringPi-Python

from james.plugin import *

# FIXME!
# class RaspberryThread(PluginThread):

#     def __init__(self, plugin, host, volume1, volume2, fade_time, url, commands = []):
#         super(RaspberryThread, self).__init__(plugin)
#         self.host = host
#         self.volume1 = str(volume1)
#         self.volume2 = str(volume2)
#         self.fade_time = str(fade_time)
#         self.url = url
#         self.commands = commands

#     def work(self):
#         self.plugin.exec_mpc(['clear'])
#         self.plugin.load_online_playlist(self.url)
#         if self.volume1 > self.volume2:
#             # sleep mode
#             self.plugin.exec_mpc(['volume', self.volume1])
#             self.plugin.exec_mpc(['play'])
#         self.plugin.exec_mpc(['volume', self.volume1])
#         command = ['/usr/bin/mpfade',
#                    str(self.fade_time),
#                    str(self.volume2),
#                    self.host]
#         args = self.plugin.core.utils.list_unicode_cleanup(command)
#         self.plugin.core.utils.popenAndWait(args)
#         return(["MPD Fade ended"])

#     def on_exit(self, result):
#         self.plugin.mpd_callback(result, self.commands)


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

    def rasp_button_callback(self, args):
        pass

descriptor = {
    'name' : 'raspberry',
    'help' : 'Interface to RaspberryPi',
    'command' : 'rasp',
    'mode' : PluginMode.MANAGED,
    'class' : RaspberryPlugin
}

