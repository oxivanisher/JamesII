import wiringpi
import time
import threading
import math

from james.plugin import *


class BlinkLed(object):
    # LED blink class, returns true when finished
    def __init__(self, thread, pin, amount, cycles=5):
        self.thread = thread
        self.pin = pin
        self.amount = amount * 2 - 1
        self.cycles = cycles
        self.counter = 0
        self.led_state = True
        self.thread.set_pin(self.pin, True)

    def check(self):
        self.counter += 1
        if self.amount > 0:
            if self.counter >= self.cycles:
                if self.led_state:
                    self.thread.set_pin(self.pin, False)
                    self.led_state = False
                else:
                    self.thread.set_pin(self.pin, True)
                    self.led_state = True

                self.counter = 0
                self.amount -= 1

        if self.amount <= 0:
            return True
        else:
            return False


class RaspberryThread(PluginThread):

    def __init__(self, plugin, button_pins, switch_pins, led_pins, pull_up):
        super(RaspberryThread, self).__init__(plugin)
        self.button_pins = button_pins
        self.switch_pins = switch_pins
        self.led_pins = led_pins
        self.pin_state_cache = {}
        # wiringpi = wiringpi2.GPIO(wiringpi2.GPIO.WPI_MODE_PINS)
        # wiringpi.wiringPiSetup()
        # wiringpi.wiringPiSetupSys()
        wiringpi.wiringPiSetupGpio()
        self.led_blink_list = []
        self.pull_up = pull_up
        self.loop_sleep = 100

    def rasp_init(self):
        for pin in list(self.pull_up.keys()):
            if self.pull_up[pin]:
                self.logger.info("Raspberry plugin pulling up pin %s" % pin)
                wiringpi.pullUpDnControl(int(pin), 2)
            else:
                self.logger.info("Raspberry plugin pulling down pin %s" % pin)
                wiringpi.pullUpDnControl(int(pin), 1)

        self.pin_state_cache['switch'] = {}
        for pin in self.switch_pins:
            wiringpi.pinMode(pin, 0)
            self.pin_state_cache['switch'][pin] = {'count': 0,
                                                   'state': self.read_pin(pin)}

        for pin in self.led_pins:
            wiringpi.pinMode(pin, 1)
            wiringpi.digitalWrite(pin, 0)

        self.pin_state_cache['buttons'] = {}
        for pin in self.button_pins:
            wiringpi.pinMode(pin, 0)
            initial_state = self.read_pin(pin)
            self.pin_state_cache['buttons'][pin] = {'count': 0,
                                                    'state': initial_state,
                                                    'start': initial_state,
                                                    'pressed': 0}

    def work(self):
        self.rasp_init()

        active = True
        # loop_count = 0
        # millis = int(round(time.time() * 1000)) - 10
        # last_diff = 10

        # sleeping for 1/100 sec seems to be a good value for raspberry
        # nope, pi zero w does not like that. the logic was changed to use self.loop_sleep in millis and not use
        # counting but calculating the time a button was pressed with timestamps
        while active:
            # this magic calculates the next sleep time based on the last run to about 0.01 sec
            loop_start = time.time() * 1000

            # new_millis = int(round(time.time() * 1000))
            # diff = new_millis - millis
            # sleep_time = (20 - ((diff + last_diff )/ 2 )) * 0.001
            # last_diff = diff
            # millis = new_millis

            # debug output
            # loop_count += 1
            # if (loop_count % 1000) == 0:
            #     print "loop count: %s" % loop_count
            #     for pin in self.pin_state_cache['switch']:
            #         print "switch pin count: %s - %s" % (pin, self.pin_state_cache['switch'][pin]['count'])
            #     for pin in self.pin_state_cache['buttons']:
            #         print "button pin count: %s - %s" % (pin, self.pin_state_cache['buttons'][pin])
            #     self.logger.debug("Rasp Worker Debug: time:       %s" % int(time.time()))
            #     self.logger.debug("Rasp Worker Debug: sleep_time: %s" % sleep_time)
            #     self.logger.debug("Rasp Worker Debug: diff:       %s" % diff)

            # see if we must blink with some leds
            for blink in self.led_blink_list:
                if blink.check():
                    self.led_blink_list.remove(blink)

            self.plugin.worker_lock.acquire()
            # see if I must shut myself down
            if self.plugin.worker_exit:
                active = False
                self.plugin.worker_lock.release()
                continue
            # see if we must switch some leds on
            for pin in self.plugin.waiting_leds_on:
                self.set_pin(pin, True)
            # see if we must switch some leds off
            for pin in self.plugin.waiting_leds_off:
                self.set_pin(pin, False)
            # see if we must create new blink objects from main thread
            for (pin, amount, duration) in self.plugin.waiting_leds_blink:
                self.led_blink(pin, amount, duration)

            self.plugin.waiting_leds_on = []
            self.plugin.waiting_leds_off = []
            self.plugin.waiting_leds_blink = []

            self.plugin.worker_lock.release()

            # check for pressed buttons
            for pin in self.button_pins:
                current_state = self.read_pin(pin)
                if current_state != self.pin_state_cache['buttons'][pin]['state']:
                    self.pin_state_cache['buttons'][pin]['state'] = current_state
                    button_state_changed = True
                    self.logger.debug("Button state change registered for pin %s" % pin)
                else:
                    button_state_changed = False

                # button is newly pressed
                if button_state_changed and self.pin_state_cache['buttons'][pin]['count'] == 0 and \
                        self.pin_state_cache['buttons'][pin]['state'] != self.pin_state_cache['buttons'][pin]['start']:
                    self.logger.debug("Button press registered for pin %s" % pin)
                    self.pin_state_cache['buttons'][pin]['pressed'] = time.time()

                # button is still pressed this loop
                if not button_state_changed and self.pin_state_cache['buttons'][pin]['state'] != \
                        self.pin_state_cache['buttons'][pin]['start']:
                    self.pin_state_cache['buttons'][pin]['count'] += 1

                # button is released
                if button_state_changed and self.pin_state_cache['buttons'][pin]['state'] == \
                        self.pin_state_cache['buttons'][pin]['start']:
                    duration = int(math.floor(time.time() - self.pin_state_cache['buttons'][pin]['pressed']))
                    self.logger.debug("Button on pin %s release registered after %s seconds" % (pin, duration))
                    self.plugin.core.add_timeout(0, self.plugin.on_button_press, pin, duration)
                    if len(self.led_pins) > 2:
                        self.led_blink(2, duration)
                    self.pin_state_cache['buttons'][pin]['count'] = 0
                    self.pin_state_cache['buttons'][pin]['pressed'] = 0

            # check for switch states
            for pin in self.switch_pins:
                new_state = self.read_pin(pin)
                if self.pin_state_cache['switch'][pin]['state'] == new_state:
                    self.pin_state_cache['switch'][pin]['count'] += 1
                else:
                    self.logger.debug("Switch change registered")
                    self.plugin.core.add_timeout(0, self.plugin.on_switch_change, pin, new_state)
                    self.pin_state_cache['switch'][pin]['state'] = new_state
                    self.pin_state_cache['switch'][pin]['count'] = 0

            sleep_time = self.loop_sleep - (time.time() * 1000 - loop_start)
            # don't sleep if we should shut down
            if sleep_time > 0 and active:
                time.sleep(sleep_time / 1000)

        # enable all leds on exit
        for pin in self.led_pins:
            self.set_pin(pin, True)
        # and disable all buttons and switches
        for pin in self.button_pins + self.switch_pins:
            self.set_pin(pin, False)
        self.logger.info("All sub threads of raspberry worker ended")

    # rasp gpio methods
    def led_blink(self, pin, amount=1, cycles=5):
        self.led_blink_list.append(BlinkLed(self, pin, amount, cycles))

    def set_pin(self, pin, mode):
        if mode:
            wiringpi.digitalWrite(pin, 1)
        else:
            wiringpi.digitalWrite(pin, 0)

    def read_pin(self, pin):
        return wiringpi.digitalRead(pin)

    # called when the worker ends
    def on_exit(self, result):
        self.logger.info("Raspberry worker exited")


class RaspberryPlugin(Plugin):

    def __init__(self, core, descriptor):

        super(RaspberryPlugin, self).__init__(core, descriptor)

        self.rasp_thread = False
        self.worker_exit = False
        self.worker_lock = threading.Lock()
        self.waiting_leds_on = []
        self.waiting_leds_off = []
        self.waiting_leds_blink = []
        self.messages_waiting_count = 0

        self.pull_up = {}
        if 'pull_up' in list(self.config['nodes'][self.core.hostname].keys()):
            self.pull_up = self.config['nodes'][self.core.hostname]['pull_up']

        self.led_pins = []
        if 'led_pins' in list(self.config['nodes'][self.core.hostname].keys()):
            for led_pin in self.config['nodes'][self.core.hostname]['led_pins']:
                self.led_pins.append(led_pin)

        self.button_pins = []
        self.button_commands = {}
        try:
            for command in self.utils.convert_from_unicode(self.config['nodes'][self.core.hostname]['buttons']):
                self.button_commands[(command['pin'], command['seconds'])] = command['command'].split()
                self.button_pins.append(command['pin'])
        except Exception as e:
            self.logger.debug("Raspberry Button load Exception (%s)" % e)

        self.switch_pins = []
        self.switch_commands = {}
        if 'switches' in list(self.config['nodes'][self.core.hostname].keys()):
            try:
                for command in self.utils.convert_from_unicode(self.config['nodes'][self.core.hostname]['switches']):
                    self.switch_commands[(command['pin'], True)] = command['cmd_on'].split()
                    self.switch_commands[(command['pin'], False)] = command['cmd_off'].split()
                    self.switch_pins.append(command['pin'])
            except Exception as e:
                self.logger.debug("Raspberry Switch load Exception (%s)" % e)

        if core.os_username == 'root':
            self.commands.create_subcommand('quit', 'Quits the raspberry worker', self.cmd_rasp_quit)
            self.commands.create_subcommand('start', 'Starts the raspberry worker', self.cmd_rasp_start)
            led_commands = self.commands.create_subcommand('led', 'Led control commands', None)
            led_commands.create_subcommand('on', 'Switches on given LED', self.cmd_led_on)
            led_commands.create_subcommand('off', 'Switches off given LED', self.cmd_led_off)
            led_commands.create_subcommand('show', 'Shows configured LEDs', self.cmd_show_leds)
            show_commands = self.commands.create_subcommand('show', 'Show commands for buttons and switches', None)
            show_commands.create_subcommand('buttons', 'Shows button commands', self.cmd_show_buttons)
            show_commands.create_subcommand('switches', 'Shows switch commands', self.cmd_show_switches)

    # plugin methods
    def start(self):
        self.start_worker()
        count = 0
        if len(self.led_pins):
            for led_num in range(len(self.led_pins)):
                self.blink_led(led_num, (len(self.led_pins) - count) * 3, 2)
                count += 1
            if len(self.core.get_present_users_here()):
                self.turn_off_led(len(self.led_pins)-1)
            else:
                self.turn_on_led(len(self.led_pins)-1)

    def terminate(self):
        self.worker_must_exit()
        self.wait_for_threads(self.worker_threads)

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

    def cmd_show_leds(self, args):
        ret = []
        counter= 0
        for pin in self.led_pins:
            ret.append("LED #: %2s, GPIO Pin: %2s" % (counter, pin))
            counter += 1
        return ret

    def cmd_led_on(self, args):
        args = self.utils.list_unicode_cleanup(args)
        try:
            len_num = int(args[0])
            self.turn_on_led(len_num)
            return ["Led %s will be switched on" % len_num]
        except Exception as e:
            return ["Syntax error (%s)" % e]

    def cmd_led_off(self, args):
        args = self.utils.list_unicode_cleanup(args)
        try:
            len_num = int(args[0])
            self.turn_off_led(len_num)
            return ["Led %s will be switched off" % len_num]
        except Exception as e:
            return ["Syntax error (%s)" % e]
    
    def cmd_rasp_quit(self, args):
        return self.worker_must_exit()

    def cmd_rasp_start(self, args):
        return self.start_worker()

    # utility methods for the gpio
    def turn_on_led(self, led_num):
        if len(self.led_pins) < led_num:
            self.logger.warning("No LED # %s configured" % led_num)
        else:
            self.logger.debug("Turning LED # %s on" % led_num)
            self.worker_lock.acquire()
            self.waiting_leds_on.append(self.led_pins[led_num])
            self.worker_lock.release()

    def turn_off_led(self, led_num):
        if len(self.led_pins) < led_num:
            self.logger.warning("No LED # %s configured" % led_num)
        else:
            self.logger.debug("Turning LED # %s off" % led_num)
            self.worker_lock.acquire()
            self.waiting_leds_off.append(self.led_pins[led_num])
            self.worker_lock.release()

    def blink_led(self, led_num, amount=1, sleep=5):
        if len(self.led_pins) < led_num:
            self.logger.warning("No LED # %s configured" % led_num)
        else:
            self.logger.debug("Blinking led # %s" % led_num)
            self.worker_lock.acquire()
            self.waiting_leds_blink.append((self.led_pins[led_num], amount, sleep))
            self.worker_lock.release()

    # methods for worker process
    def on_button_press(self, pin, duration):
        self.logger.debug("Button press registered")
        try:
            self.send_command(self.button_commands[(pin, duration)])
        except Exception as e:
            self.logger.debug("Button press error (%s)" % e)

    def on_switch_change(self, pin, new_state):
        self.logger.debug("Switch change registered")
        try:
            self.send_command(self.switch_commands[(pin, new_state)])
        except Exception as e:
            self.logger.debug("Switch change error (%s)" % e)

    # worker control methods
    def start_worker(self):
        self.worker_lock.acquire()
        self.worker_exit = False
        self.worker_lock.release()
        self.rasp_thread = RaspberryThread(self, self.button_pins, self.switch_pins, self.led_pins, self.pull_up)
        self.rasp_thread.start()
        self.worker_threads.append(self.rasp_thread)
        msg = "Raspberry worker starting"
        self.logger.info(msg)
        return [msg]

    def worker_must_exit(self):
        self.worker_lock.acquire()
        self.worker_exit = True
        self.worker_lock.release()
        msg = "Raspberry worker is ordered to exit"
        self.logger.debug(msg)
        return [msg]

    # james system event handler
    def process_presence_event(self, presence_before, presence_now):
        self.logger.debug("Processing presence event")

        if len(presence_now):
            if len(self.led_pins):
                self.logger.debug("Processing presence event and enabling last LED")
                self.core.add_timeout(0, self.turn_off_led, len(self.led_pins)-1)
                self.messages_waiting_count = 0
        else:
            if len(self.led_pins):
                self.logger.debug("Processing presence event and disabling last LED")
                self.core.add_timeout(0, self.turn_on_led, len(self.led_pins)-1)

    def process_message(self, message):
        self.logger.debug("Processing msg event")

        # at home
        if len(self.core.get_present_users_here()):
            if message.level == 1:
                if len(self.led_pins):
                    self.blink_led(0, 3)
            if message.level == 2:
                if len(self.led_pins) > 1:
                    self.blink_led(1, 3)
            if message.level == 3:
                if len(self.led_pins) > 3:
                    self.blink_led(2, 3)
        else:
            self.messages_waiting_count += 1

    def alert(self, args):
        self.logger.debug("Processing alert event")

        # at home
        if len(self.core.get_present_users_here()):
            if len(self.led_pins) > 1:
                self.blink_led(1, 2)


descriptor = {
    'name': 'raspberry',
    'help_text': 'Interface to RaspberryPi',
    'command': 'rasp',
    'mode': PluginMode.MANAGED,
    'class': RaspberryPlugin,
    'detailsNames': {}
}
