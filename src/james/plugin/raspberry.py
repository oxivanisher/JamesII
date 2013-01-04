
import subprocess
import sys
import wiringpi

#https://github.com/WiringPi/WiringPi-Python

from james.plugin import *

class RaspberryThread(PluginThread):

    def __init__(self, plugin, read_pins, write_pins):
        super(RaspberryThread, self).__init__(plugin)
        self.gpio = wiringpi.GPIO(wiringpi.GPIO.WPI_MODE_PINS)
        self.read_pins = read_pins
        self.write_pins = write_pins
        self.plugin = plugin
        self.led_state = []

    def get_led_state(self, state):
        # Lock.acquire()
        return self.led_state
        # Lock.release()
        pass

    def set_led_state(self, state):
        # Lock.acquire()
        self.led_state = state
        # Lock.release()
        pass

    def init_wiringpi(self):
        # set modes on pins
        for pin in self.read_pins:
            self.gpio.pinMode(pin, self.gpio.INPUT)
        
        for pin in self.write_pins:
            self.gpio.pinMode(pin, self.gpio.OUTPUT)

    def work(self):
        self.init_wiringpi()

        active = True
        while active:
        # read instructions to set leds
            state = self.get_led_state()
        # self.led_state
        # [0, 1, 2] = 0: no change, 1: switch on, 2: switch off
            for pin in self.read_pins:
                self.plugin.core.add_timeout(0, self.plugin.on_button_press, pin)

            # do something meaningful
            self.set_led_state(state)
            # sleep

    def read_pin(self, pin):
        return self.gpio.digitalRead(pin)

    def set_pin(self, led_id, mode):
        if mode:
            self.gpio.digitalWrite(led_id, self.gpio.HIGH)
        else:
            self.gpio.digitalWrite(led_id, self.gpio.LOW)
        
    def on_exit(self, result):
        self.plugin.on_worker_exit()

class RaspberryPlugin(Plugin):

    def __init__(self, core, descriptor):

        super(RaspberryPlugin, self).__init__(core, descriptor)

        if core.os_username == 'root':
            self.commands.create_subcommand('test', 'Test command for raspberry. turns on the 2nd led', self.cmd_rasp_test)

    def start(self):
        #self.rasp_thread = RaspberryThread(self)

    def cmd_rasp_test(self, args):
        self.rasp_thread.set_led_state(state)
        pass

    # methods called from worker process
    def on_button_press(self, args):
        pass

    def on_worker_exit(self):
        pass

descriptor = {
    'name' : 'raspberry',
    'help' : 'Interface to RaspberryPi',
    'command' : 'rasp',
    'mode' : PluginMode.MANAGED,
    'class' : RaspberryPlugin
}
