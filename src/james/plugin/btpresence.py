import os
import subprocess
import time
import atexit
import json
import random
from bluetooth import *

from james.plugin import *


# FIXME add net scan with "arp-scan -I $NETINTERFACE -q --localnet | sort -t . -k 1,1n -k 2,2n -k 3,3n -k 4,4n"
# where do we keep the store of mac addresses? objects, objects, objects

# no longer use l2ping?
# https://chatgpt.com/c/68e6bc08-2580-832e-bc2b-df734c272a32

class BTPresencePlugin(Plugin):

    def __init__(self, core, descriptor):
        super(BTPresencePlugin, self).__init__(core, descriptor)

        self.users_here = []  # current value of users here which gets sent all the time
        self.tmp_users_here = []  # self.users_here cached to handle missing-counter

        # check required tools
        self.tools = {'hcitool': '/usr/bin/hcitool',
                      'l2ping': '/usr/bin/l2ping',
                      'bluez-simple-agent': 'bluez-simple-agent'}

        for tool in list(self.tools.keys()):
            if os.path.isfile(self.tools[tool]):
                self.logger.debug("%s found in %s" % (tool, self.tools[tool]))
            else:
                self.logger.warning("%s NOT found in %s" % (tool, self.tools[tool]))

        if os.path.isfile(self.tools['hcitool']):
            # self.commands.create_subcommand('discover', 'Scan for visible bluetooth devices', self.discover)
            self.commands.create_subcommand('test', 'Test for local bluetooth devices', self.test)
            if self.core.os_username == 'root':
                self.commands.create_subcommand('persons', 'Shows the persons currently detected', self.show_persons)
                self.commands.create_subcommand('presence', 'Run a manual presence check', self.presence_check)
                self.commands.create_subcommand('pair', 'Pair with a device (add BT MAC)', self.prepare_pair)
                always_at_home_command = self.commands.create_subcommand('always_at_home',
                                                                         'Override to be always at home',
                                                                         None)
                always_at_home_command.create_subcommand('on', 'Activate always at home', self.always_at_home_on)
                always_at_home_command.create_subcommand('off', 'Deactivate always at home', self.always_at_home_off)

            errors_command = self.commands.create_subcommand('errors', 'Show and clear gathered l2ping errors', None)
            errors_command.create_subcommand('clear', 'Clear l2ping errors', self.errors_clear)
            errors_command.create_subcommand('show', 'Show l2ping errors', self.errors_show)

        atexit.register(self.save_state)
        self.persons_btpresence_file = os.path.join(os.path.expanduser("~"), ".james_btpresence_status")
        self.l2ping_errors_file = os.path.join(os.path.expanduser("~"), ".james_btpresence_errors")
        self.proxy_send_lock = False
        self.load_saved_state()

        self.presence_checks = 0
        self.presence_updates = 0
        self.alwaysAtHome = False
        self.load_state('presence_checks', 0)
        self.load_state('presence_updates', 0)
        self.load_state('alwaysAtHome', False)
        self.last_presence_check_start = 0
        self.last_presence_check_end = 0
        self.last_presence_check_duration = 0
        self.current_presence_sleep = 0
        self.missing_count = -1
        self.always_at_home = False
        self.l2ping_errors = {}
        self.need_to_terminate = False
        self.next_presence_keepalive_run = 0
        self.next_presence_check_run = 0
        self.presence_check_error_count = 0 # this should not be required ... but here we are

    def presence_event(self, users):
        if self.always_at_home:
            users += ['always_at_home']
        users = sorted(list(set(users)))
        sys_msg = f"Publish presence change to: [{', '.join(users)}]"
        self.logger.debug(sys_msg)
        self.system_message_add(sys_msg)
        self.core.presence_event(self.name, users)

    def start(self):
        if self.core.os_username == 'root':
            # wait 3 seconds before working
            self.core.add_timeout(3, self.presence_check_daemon)

        # publish the btpresence state (core only publishes something, if it has changed.
        # so loading the state from file should be safe.)
        self.core.add_timeout(1, self.presence_keepalive_daemon)

    def load_saved_state(self):
        try:
            # load saved presence persons
            self.logger.debug(f"Loading btpresence status from {self.persons_btpresence_file}")
            presence_file = open(self.persons_btpresence_file, 'r')
            self.users_here = json.loads(presence_file.read())
            presence_file.close()
        except IOError:
            pass
        pass

        try:
            # load saved presence persons
            self.logger.debug(f"Loading l2ping errors from {self.l2ping_errors_file}")
            errors_file = open(self.l2ping_errors_file, 'r')
            self.l2ping_errors = json.loads(errors_file.read())
            errors_file.close()
        except IOError:
            pass
        pass

    def save_state(self, verbose=False):
        try:
            presence_file = open(self.persons_btpresence_file, 'w')
            presence_file.write(json.dumps(self.users_here))
            presence_file.close()
            self.logger.debug(f"Saving persons status to {self.persons_btpresence_file}")
        except IOError:
            sys_msg = "Could not save persons status to file!"
            self.system_message_add(sys_msg)
            self.logger.warning(sys_msg)

        try:
            errors_file = open(self.l2ping_errors_file, 'w')
            errors_file.write(json.dumps(self.l2ping_errors))
            errors_file.close()
            self.logger.debug(f"Saving l2ping errors to {self.l2ping_errors_file}")
        except IOError:
            sys_msg = "Could not save l2ping errors to file!"
            self.system_message_add(sys_msg)
            self.logger.warning(sys_msg)

    # command methods
    def test(self, args):
        devices = {}
        lines = self.utils.popen_and_wait([self.tools['hcitool'], 'dev'])
        lines = self.utils.list_unicode_cleanup(lines)
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                devices[values[1]] = values[0]
        return devices

    def prepare_pair(self, args):
        key = random.randint(1000, 9999)
        pair_msg = "Bluetooth pairing key is: %s" % key
        lines = self.utils.popen_and_wait([self.tools['bluez-simple-agent'], 'hci0', args[0], 'remove'])
        pair_data = [args[0], key]
        self.core.add_timeout(0, self.pair, pair_data)
        return pair_msg

    def pair(self, pair_data):
        p = subprocess.Popen([self.tools['bluez-simple-agent'],
                              'hci0', pair_data[0]],
                             stdout=subprocess.PIPE,
                             stdin=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        pair_out = p.communicate(input=bytes(pair_data[1]) + b'\n')[0]
        self.logger.debug("BT Logging output: %s" % pair_out)

    def show_persons(self, args):
        ret = []
        for person in self.users_here:
            ret.append("%10s is here" % person)
        return ret

    def always_at_home_on(self, args):
        self.always_at_home = True
        self.logger.info("Presence always_at_home override ENABLED, sending presence status: "
                         "%s@%s" % (self.always_at_home, self.core.location))
        self.presence_event(self.users_here)
        return ["Always at home override ENABLED"]

    def always_at_home_off(self, args):
        self.always_at_home = False
        self.logger.info("Presence always_at_home override DISABLED, sending presence status: "
                         "%s@%s" % (self.always_at_home, self.core.location))
        self.presence_event(self.users_here)
        return ["Always at home override DISABLED"]

    def errors_clear(self, args):
        self.logger.info("Clearing gathered l2ping errors")
        self.l2ping_errors = {}
        return ["l2ping errors cleared"]

    def errors_show(self, args):
        self.logger.debug("Showing gathered l2ping errors")
        ret = []
        if len(self.l2ping_errors.keys()):
            for key in sorted(self.l2ping_errors.keys()):
                ret.append(f"{key}: {self.l2ping_errors[key]}")
        else:
            ret.append("No l2ping errors gathered")
        return ret

    # ensure to send our presence info at least every self.core.config['presence_timeout']
    def presence_keepalive_daemon(self):
        # stop checking for presence if the core wants to quit
        if self.core.terminating:
            return

        if time.time() >  self.next_presence_keepalive_run:
            self.next_presence_keepalive_run = time.time() + self.core.config['core']['presence_timeout'] + random.randint(-15, -5)
            self.presence_event(self.users_here)

        self.core.add_timeout(3, self.presence_keepalive_daemon)

    # presence daemon methods
    def presence_check_daemon(self):
        if self.core.terminating:
            return

        timeout = 10
        if time.time() > self.next_presence_check_run:
            self.presence_check(None)

            self.next_presence_check_run = time.time() + self.config['sleep_short'] + random.randint(-2, 2)
            if len(self.users_here):
                self.next_presence_check_run = time.time() + self.config['sleep_long'] + random.randint(-2, 2)

        time_remaining = self.next_presence_check_run - time.time()
        if time_remaining > timeout:
            self.core.add_timeout(timeout, self.presence_check_daemon)
        else:
            self.core.add_timeout(time_remaining, self.presence_check_daemon)

    def presence_check(self, args):
        self.last_presence_check_start = time.time()
        # All this try/except should not be required ... but for some reason, we sometimes are not allowed to spawn a
        # l2ping thread. One missing ping is not a problem, lets see how bad it is (and migrate to a python only
        # solution down the road!)

        try:
            self.worker_threads.append(self.core.spawn_subprocess(self.presence_check_worker,
                                                                  self.presence_check_worker_callback,
                                                                  None,
                                                                  self.logger))
            if self.presence_check_error_count:
                sys_msg = f"The btpresence check was able to recover after {self.presence_check_error_count} checks"
                self.logger.warning(sys_msg)
                self.system_message_add(sys_msg)
            self.presence_check_error_count = 0
        except Exception as e:
            self.presence_check_error_count += 1
            # Simulating not having found any device on l2ping error
            self.presence_check_worker_callback([])

    def presence_check_worker(self):
        self.logger.debug('Starting bluetooth presence scan for <%s>' % self.core.location)
        mac_addresses = []
        for person in list(self.core.config['persons'].keys()):
            try:
                if self.core.config['persons'][person]['bt_devices']:
                    for name in list(self.core.config['persons'][person]['bt_devices'].keys()):
                        mac = self.core.config['persons'][person]['bt_devices'][name]
                        ret = self.utils.popen_and_wait([self.tools['l2ping'], '-c', '1', mac])
                        clear_list = [s for s in ret if s != '']

                        self.logger.warninf(f"tmp debugging strange error: {clear_list}")

                        for line in clear_list:
                            if "bytes from" in line:
                                mac_addresses.append(mac)
                            if "Can't connect:" in line:
                                error_str = line[15:]
                                if error_str == "Host is down":
                                    self.logger.debug(f'Bluetooth host {mac} is down')
                                else:
                                    error_msg = f'Bluetooth l2ping error for {mac}: {error_str}'

                                    if error_str not in self.l2ping_errors.keys():
                                        self.l2ping_errors[error_str] = 0
                                        self.send_broadcast(error_msg)

                                    self.system_message_add(error_msg)
                                    self.logger.warning(error_msg)
                                    self.l2ping_errors[error_str] += 1

            except KeyError:
                # person has no bt_devices
                pass
            except Exception:
                # probably parse error from command
                pass
        return mac_addresses

    def presence_check_worker_callback(self, mac_addresses):
        self.logger.debug(f"Presence scan finished, found the following macs: {', '.join(mac_addresses)}")
        self.presence_checks += 1
        self.last_presence_check_end = time.time()
        self.last_presence_check_duration = self.last_presence_check_end - self.last_presence_check_start
        persons_detected = []

        # cleanup remaining worker threads
        self.worker_threads = [t for t in self.worker_threads if t.is_alive()]

        # registering the person for which devices as detected
        for mac_address in mac_addresses:
            for person in list(self.core.config['persons'].keys()):
                if 'bt_devices' in self.core.config['persons'][person].keys():
                    for device in self.core.config['persons'][person]['bt_devices'].values():
                        if device.lower() == mac_address.lower():
                            persons_detected.append(person)

        persons_detected = sorted(list(set(persons_detected)))
        self.logger.debug(f"Detected the following persons: {', '.join(persons_detected)}")

        # if something changed, increment the presence_updates counter
        if self.tmp_users_here != persons_detected:
            self.presence_updates += 1
            if len(persons_detected):
                self.logger.debug(f"Change detected: {', '.join(persons_detected)} at {self.core.location}")
            else:
                self.logger.debug(f"Change detected: Nobody at {self.core.location}")

        persons_left = set(self.tmp_users_here).difference(persons_detected)
        persons_entered = set(persons_detected).difference(self.tmp_users_here)

        self.logger.debug(f"Persons left: {', '.join(persons_left)}")
        self.logger.debug(f"Persons entered: {', '.join(persons_entered)}")

        # saving the actual persons detected to temp var
        self.tmp_users_here = persons_detected

        # use the missing-counter to be able to work around BT devices which not always answer ping
        if len(self.tmp_users_here) == 0:
            self.missing_count += 1
            if self.missing_count == 0:
                # this only happens on the very first run after startup to suppress the msg
                pass
            elif self.missing_count < int(self.config['miss_count']):
                self.logger.debug(f"Missing-counter increased to {self.missing_count} of {self.config['miss_count']}")
            elif self.missing_count == int(self.config['miss_count']):
                self.users_here = self.tmp_users_here
                self.logger.info(f"Missing-counter reached its max of {self.config['miss_count']}. "
                                 f"Sending presence event: {self.users_here}@{self.core.location}")
                self.presence_event(self.users_here)
            else:
                # since the count keeps counting, just ignore it
                self.logger.debug(f"Missing-counter now at {self.missing_count}, doing nothing")

        else:
            # making sure, the missing counter is reset every time someone is around
            self.missing_count = 0
            if self.tmp_users_here != self.users_here:
                self.logger.debug(f"Detected persons changed while somebody is at {self.core.location}. "
                                  f" Sending presence event: {self.users_here}@{self.core.location}")
                self.users_here = self.tmp_users_here
                self.presence_event(self.users_here)

    def process_discovery_event(self, msg):
        if not self.proxy_send_lock:
            if msg[0] == 'hello':
                self.proxy_send_lock = True
                self.core.add_timeout(3, self.process_discovery_event_callback)

    def process_discovery_event_callback(self):
        self.logger.debug('Publishing bluetooth presence event')
        self.proxy_send_lock = False
        self.presence_event(self.users_here)

    def terminate(self):
        self.need_to_terminate = True
        # self.wait_for_threads()

    def return_status(self, verbose=False):
        l2ping_errors = []
        for key in sorted(self.l2ping_errors.keys()):
            l2ping_errors.append(f"{key}: {self.l2ping_errors[key]}")

        ret = {'presence_checks': self.presence_checks, 'presence_updates': self.presence_updates,
               'alwaysAtHome': self.always_at_home, 'last_presence_check_start': self.last_presence_check_start,
               'last_presence_check_end': self.last_presence_check_end,
               'last_presence_check_duration': self.last_presence_check_duration,
               'current_presence_sleep': self.current_presence_sleep, 'current_presence_state': self.users_here,
               'nextCheckIn': self.last_presence_check_end + self.current_presence_sleep - time.time(),
               'l2ping_errors': l2ping_errors}
        return ret


descriptor = {
    'name': 'btpresence',
    'help_text': 'Bluetooth presence detection plugin',
    'command': 'btpresence',
    'mode': PluginMode.MANAGED,
    'class': BTPresencePlugin,
    'detailsNames': {'presence_checks': "Run presence checks",
                     'presence_updates': "Presence status changes",
                     'alwaysAtHome': "Always at home override active",
                     'last_presence_check_start': "Last Proximity check start",
                     'last_presence_check_end': "Last Proximity check end",
                     'current_presence_sleep': "Current sleep time",
                     'current_presence_state': "Current presence state",
                     'nextCheckIn': "Next check in",
                     'last_presence_check_duration': "Last Proximity check duration",
                     'l2ping_errors': "Gathered l2ping errors"}
}
