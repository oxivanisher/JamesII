
import sys
import wiringpi
import time
import threading

#https://github.com/WiringPi/WiringPi-Python

from james.plugin import *

class RaspberryThread(PluginThread):

    def __init__(self, plugin, button_pins, switch_pins, led_pins):
        # FIXME i must become a singleton!
        super(RaspberryThread, self).__init__(plugin)
        self.button_pins = button_pins
        self.switch_pins = switch_pins
        self.led_pins = led_pins
        self.plugin = plugin
        self.pin_state_cache = {}
        self.gpio = wiringpi.GPIO(wiringpi.GPIO.WPI_MODE_PINS)

    def rasp_init(self):
        self.pin_state_cache['buttons'] = {}
        for pin in self.button_pins:
            self.gpio.pinMode(pin, self.gpio.INPUT)
            self.pin_state_cache['buttons'][pin] = 0

        self.pin_state_cache['switch'] = {}
        for pin in self.switch_pins:
            self.gpio.pinMode(pin, self.gpio.INPUT)
            current_state = self.read_pin(pin)
            self.pin_state_cache['switch'][pin] = { 'count' : 0, 'state' : current_state}
        
        for pin in self.led_pins:
            self.gpio.pinMode(pin, self.gpio.OUTPUT)
            self.gpio.digitalWrite(pin, self.gpio.LOW)

    def work(self):
        self.rasp_init()

        active = True
        loop_count = 0

        while active:
            loop_count += 1
            if (loop_count % 1000) == 0:
                self.led_blink(0, 1)

            self.plugin.worker_lock.acquire()
            # see if i must shut myself down
            if self.plugin.worker_exit:
                active = False
            # see if we must switch some leds on
            for pin in self.plugin.waiting_leds_on:
                self.set_led(pin, True)
            # see if we must switch some leds off
            for pin in self.plugin.waiting_leds_off:
                self.set_led(pin, False)
            # see if we must blink with some leds
            for (pin, amount, duration) in self.plugin.waiting_leds_blink:
                self.led_blink(pin, amount, duration)

            self.plugin.waiting_leds_on = []
            self.plugin.waiting_leds_off = []
            self.plugin.waiting_leds_blink = []

            self.plugin.worker_lock.release()

            # check for pressed buttons
            for pin in self.button_pins:
                if not self.read_pin(pin):
                    self.pin_state_cache['buttons'][pin] += 1
                else:
                    # 100 counts are ~+ 1 second
                    if self.pin_state_cache['buttons'][pin] > 500:
                        self.plugin.core.add_timeout(0, self.plugin.on_extended_button_press, pin)
                    if self.pin_state_cache['buttons'][pin] > 200:
                        self.plugin.core.add_timeout(0, self.plugin.on_long_button_press, pin)
                    elif self.pin_state_cache['buttons'][pin] > 100:
                        self.plugin.core.add_timeout(0, self.plugin.on_medium_button_press, pin)
                    elif self.pin_state_cache['buttons'][pin] > 1:
                        self.plugin.core.add_timeout(0, self.plugin.on_short_button_press, pin)
                    self.pin_state_cache['buttons'][pin] = 0

            # check for switch states
            for pin in self.switch_pins:
                new_state = self.read_pin(pin)
                if self.pin_state_cache['switch'][pin]['state'] == new_state:
                    self.pin_state_cache['switch'][pin]['count'] += 1
                else:
                    self.plugin.core.add_timeout(0, self.plugin.on_switch_change, pin, new_state)
                    self.pin_state_cache['switch'][pin]['state'] = new_state
                    self.pin_state_cache['switch'][pin]['count'] = 0

            # sleeping for 1/100 sec seems to be a good value for raspberry
            time.sleep(0.01)

    # rasp gpio methods
    def led_blink(self, led, amount = 1, sleep = 0.05):
        for step in range(amount):
            self.set_led(led, 1)
            time.sleep(sleep)
            self.set_led(led, 0)
            time.sleep(sleep)
        
    def set_led(self, led_id, mode):
        if mode:
            self.gpio.digitalWrite(led_id, self.gpio.HIGH)
        else:
            self.gpio.digitalWrite(led_id, self.gpio.LOW)

    def read_pin(self, pin):
        return self.gpio.digitalRead(pin)

    # called when the worker ends
    def on_exit(self, result):
        for pin in self.button_pins + self.switch_pins + self.led_pins:
            self.gpio.digitalWrite(pin, self.gpio.LOW)
        self.plugin.on_worker_exit()

class RaspberryPlugin(Plugin):

    def __init__(self, core, descriptor):

        super(RaspberryPlugin, self).__init__(core, descriptor)

        self.button_pins = [4]
        self.switch_pins = [5]
        self.led_pins = [0, 1, 2, 3]

        self.rasp_thread = False
        self.worker_exit = False
        self.worker_lock = threading.Lock()
        self.waiting_leds_on = []
        self.waiting_leds_off = []
        self.waiting_leds_blink = []
        self.messages_waiting_count = 0

        if core.os_username == 'root':
            self.commands.create_subcommand('test', 'Do something with the leds', self.cmd_rasp_test)
            self.commands.create_subcommand('quit', 'Quits the raspberry worker', self.cmd_rasp_quit)
            self.commands.create_subcommand('start', 'Starts the raspberry worker', self.cmd_rasp_start)
            led_commands = self.commands.create_subcommand('led', 'Led control commands', None)
            led_commands.create_subcommand('on', 'Switches on given pin', self.cmd_led_on)
            led_commands.create_subcommand('off', 'Switches off given pin', self.cmd_led_off)

    # plugin methods
    def start(self):
        self.start_worker()
        for led in self.led_pins:
            self.blink_led(led, 3, 0.05)
        if self.core.proximity_status.status[self.core.location]:
            self.turn_off_led(3)
        else:
            self.turn_on_led(3)
    
    def terminate(self):
        self.worker_must_exit()

    # james command methods
    def cmd_rasp_test(self, args):
        self.set_led(0, 1)

    def cmd_led_on(self, args):
        args = self.core.utils.list_unicode_cleanup(args)
        try:
            pin = int(args[0])
            self.turn_on_led(pin)
            return(["Led %s will be switched on" % pin])
        except Exception as e:
            return(["Syntax error (%s)" % (e)])

    def cmd_led_off(self, args):
        args = self.core.utils.list_unicode_cleanup(args)
        try:
            pin = int(args[0])
            self.turn_off_led(pin)
            return(["Led %s will be switched off" % pin])
        except Exception as e:
            return(["Syntax error (%s)" % (e)])

    def cmd_rasp_quit(self, args):
        return self.worker_must_exit()

    def cmd_rasp_start(self, args):
        return self.start_worker()

    # utility methods for the gpio
    def turn_on_led(self, pin):
        self.worker_lock.acquire()
        self.waiting_leds_on.append(pin)
        self.worker_lock.release()

    def turn_off_led(self, pin):
        self.worker_lock.acquire()
        self.waiting_leds_off.append(pin)
        self.worker_lock.release()

    def blink_led(self, pin, amount = 1, sleep = 0.05):
        self.worker_lock.acquire()
        self.waiting_leds_blink.append((pin, amount, sleep))
        self.worker_lock.release()

    # methods for worker process
    def on_short_button_press(self, pin):
        try:
            self.blink_led(2, 1)
            if pin == 4:
                self.send_command(['mpd', 'radio', 'toggle'])
            self.send_broadcast(['Short Button %s event' % pin])
        except Exception as e:
            self.send_broadcast(['Short Button press error: %s' % (e)])
    
    def on_medium_button_press(self, pin):
        try:
            self.blink_led(2, 2)
            self.send_broadcast(['Medium Button %s event' % pin])
        except Exception as e:
            self.send_broadcast(['Medium Button press error: %s' % (e)])

    def on_long_button_press(self, pin):
        try:
            self.blink_led(2, 3)
            self.send_broadcast(['Long Button %s event' % pin])
        except Exception as e:
            self.send_broadcast(['Long Button press error: %s' % (e)])

    def on_extended_button_press(self, pin):
        try:
            self.blink_led(2, 3)
            self.send_broadcast(['Extended Button %s event' % pin])
            self.send_command(['sys', 'quit'])
        except Exception as e:
            self.send_broadcast(['Extended Button press error: %s' % (e)])

    def on_switch_change(self, pin, new_state):
        self.send_broadcast(['Switch %s changed state to %s' % (pin, new_state)])

    def on_worker_exit(self):
        self.send_broadcast(['Raspberry worker exited'])

    # worker control methods
    def start_worker(self):
        # FIXME make me singleton!
        self.worker_lock.acquire()
        self.worker_exit = False
        self.worker_lock.release()
        self.rasp_thread = RaspberryThread(self, self.button_pins, self.switch_pins, self.led_pins)
        self.rasp_thread.start()
        return self.send_broadcast(['Rasp worker starting'])
        # return(["Rasp worker starting"])

    def worker_must_exit(self):
        self.worker_lock.acquire()
        self.worker_exit = True
        self.worker_lock.release()
        return self.send_broadcast(['Rasp worker exiting'])
        # return(["Rasp worker exiting"])

    # james system event handler
    def process_proximity_event(self, newstatus):
        if self.core.config['core']['debug']:
            print("RaspberryPi Processing proximity event")
        
        if newstatus['status'][self.core.location]:
            self.turn_off_led(3)
            self.messages_waiting_count = 0
        else:
            self.turn_on_led(3)

    def process_message(self, message):
        if self.core.config['core']['debug']:
            print("RaspberryPi Processing message event")

        # at home
        if self.core.proximity_status.status[self.core.location]:
            if message.level == 1:
                self.blink_led(0, 3)
            if message.level == 2:
                self.blink_led(1, 3)
            if message.level == 3:
                self.blink_led(3, 3)
        else:
            self.messages_waiting_count += 1

descriptor = {
    'name' : 'raspberry',
    'help' : 'Interface to RaspberryPi',
    'command' : 'rasp',
    'mode' : PluginMode.MANAGED,
    'class' : RaspberryPlugin
}
