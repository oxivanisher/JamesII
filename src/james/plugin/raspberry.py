
import sys
import wiringpi
import time
import threading

#https://github.com/WiringPi/WiringPi-Python

from james.plugin import *

class BlinkLed(object):
    # led blink class, returns true when finished
    def __init__(self, thread, pin, amount, cycles = 5):
        self.thread = thread
        self.pin = pin
        self.amount = amount * 2 - 1
        self.cycles = cycles
        self.counter = 0
        self.led_state = True
        self.thread.set_led(self.pin, True)

    def check(self):
        self.counter += 1
        if self.amount > 0:
            if self.counter >= self.cycles:
                if self.led_state:
                    self.thread.set_led(self.pin, False)
                    self.led_state = False
                else:
                    self.thread.set_led(self.pin, True)
                    self.led_state = True

                self.counter = 0
                self.amount -= 1

        if self.amount <= 0:
            return True
        else:
            return False

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
        self.led_blink_list = []

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
        millis = int(round(time.time() * 1000)) - 10
        last_diff = 10

        # sleeping for 1/100 sec seems to be a good value for raspberry
        while active:
            loop_count += 1
            # this magic calculates the next sleep time based on the last run to about 0.01 sec
            new_millis = int(round(time.time() * 1000))
            diff = new_millis - millis
            sleep_time = (20 - ((diff + last_diff )/ 2 )) * 0.001
            last_diff = diff
            millis = new_millis

            # debug output
            if (loop_count % 100) == 0:
                print "Rasp Worker Debug: time:       %s" % int(time.time())
                print "Rasp Worker Debug: sleep_time: %s" % sleep_time
                print "Rasp Worker Debug: diff:       %s" % diff

            # see if we must blink with some leds
            for blink in self.led_blink_list:
                if blink.check():
                    self.led_blink_list.remove(blink)

            self.plugin.worker_lock.acquire()
            # see if i must shut myself down
            if self.plugin.worker_exit:
                active = False
                self.plugin.worker_lock.release()
                continue
            # see if we must switch some leds on
            for pin in self.plugin.waiting_leds_on:
                self.set_led(pin, True)
            # see if we must switch some leds off
            for pin in self.plugin.waiting_leds_off:
                self.set_led(pin, False)
            # see if we must create new blink objects from main thread
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
                    if (self.pin_state_cache['buttons'][pin] % 100) == 0 or self.pin_state_cache['buttons'][pin] == 2:
                        self.led_blink(1, 1)
                else:
                    # 100 counts are ~+ 1 second
                    if self.pin_state_cache['buttons'][pin]:
                        duration = int(self.pin_state_cache['buttons'][pin] / 100) + 1
                        self.plugin.core.add_timeout(0, self.plugin.on_button_press, pin, duration)
                        self.led_blink(2, duration)
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

            if sleep_time > 0:
                time.sleep(sleep_time)

        for pin in self.led_pins:
            self.set_led(pin, True)

    # rasp gpio methods
    def led_blink(self, pin, amount = 1, cycles = 5):
        self.led_blink_list.append(BlinkLed(self, pin, amount, cycles))

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

        self.led_pins = [0, 1, 2, 3]

        self.rasp_thread = False
        self.worker_exit = False
        self.worker_lock = threading.Lock()
        self.waiting_leds_on = []
        self.waiting_leds_off = []
        self.waiting_leds_blink = []
        self.messages_waiting_count = 0

        self.button_pins = []
        self.button_commands = {}
        try:
            for command in self.core.utils.convert_from_unicode(self.core.config['raspberry']['nodes'][self.core.hostname]['buttons']):
                self.button_commands[(command['pin'], command['seconds'])] = command['command'].split()
                self.button_pins.append(command['pin'])
        except Exception as e:
            print "Rasp Button load Exception (%s)" % e

        self.switch_pins = []
        self.switch_commands = {}
        try:
            for command in self.core.utils.convert_from_unicode(self.core.config['raspberry']['nodes'][self.core.hostname]['switches']):
                self.switch_commands[(command['pin'], True)] = command['cmd_on'].split()
                self.switch_commands[(command['pin'], False)] = command['cmd_off'].split()
                self.switch_pins.append(command['pin'])
        except Exception as e:
            print "Rasp Switch load Exception (%s)" % e

        if core.os_username == 'root':
            self.commands.create_subcommand('quit', 'Quits the raspberry worker', self.cmd_rasp_quit)
            self.commands.create_subcommand('start', 'Starts the raspberry worker', self.cmd_rasp_start)
            led_commands = self.commands.create_subcommand('led', 'Led control commands', None)
            led_commands.create_subcommand('on', 'Switches on given pin', self.cmd_led_on)
            led_commands.create_subcommand('off', 'Switches off given pin', self.cmd_led_off)
            show_commands = self.commands.create_subcommand('show', 'Show commands for buttons and switches', None)
            show_commands.create_subcommand('buttons', 'Shows button commands', self.cmd_show_buttons)
            show_commands.create_subcommand('switches', 'Shows switch commands', self.cmd_show_switches)

    # plugin methods
    def start(self):
        self.start_worker()
        count = 0
        for led in self.led_pins:
            self.blink_led(led, (len(self.led_pins) - count) * 3, 2)
            count += 1
        if self.core.proximity_status.status[self.core.location]:
            self.turn_off_led(3)
        else:
            self.turn_on_led(3)
    
    def terminate(self):
        self.worker_must_exit()

    # james command methods
    def cmd_show_buttons(self, args):
        ret = []
        for (pin, seconds) in sorted(self.button_commands.keys()):
            ret.append("Pin: %2s %2s secs: %s" % (pin,
                                                  seconds,
                                                  ' '.join(self.button_commands[(pin, seconds)])))
        return ret

    def cmd_show_switches(self, args):
        ret = []
        for (pin, state) in sorted(self.switch_commands.keys()):
            ret.append("Pin: %2s, %5s: %s" % (pin,
                                              state,
                                              ' '.join(self.switch_commands[(pin, state)])))
        return ret

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

    def blink_led(self, pin, amount = 1, sleep = 5):
        self.worker_lock.acquire()
        self.waiting_leds_blink.append((pin, amount, sleep))
        self.worker_lock.release()

    # methods for worker process
    def on_button_press(self, pin, duration):
        try:
            self.send_command(self.button_commands[(pin, duration)])
        except Exception as e:
            print "button press error (%s)" % e

    def on_switch_change(self, pin, new_state):
        try:
            self.send_command(self.switch_commands[(pin, new_state)])
        except Exception as e:
            print "switch change error (%s)" % e

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

    def worker_must_exit(self):
        self.worker_lock.acquire()
        self.worker_exit = True
        self.worker_lock.release()
        return self.send_broadcast(['Rasp worker exiting'])

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
