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
                self.commands.create_subcommand('always_at_home', 'Override to be always at home (true/false)',
                                                self.always_at_home)

        atexit.register(self.save_state)
        self.persons_btpresence_file = os.path.join(os.path.expanduser("~"), ".james_btpresence_status")
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
        self.messageCache = []
        self.always_at_home = False

    def presence_event(self, users):
        if self.always_at_home:
            users += ['always_at_home']
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
            self.logger.debug("Loading btpresence status from %s" % self.persons_btpresence_file)
            presence_file = open(self.persons_btpresence_file, 'r')
            self.users_here = json.loads(presence_file.read())
            presence_file.close()
        except IOError:
            pass
        pass

    def save_state(self):
        try:
            file_handler = open(self.persons_btpresence_file, 'w')
            file_handler.write(json.dumps(self.users_here))
            file_handler.close()
            self.logger.debug("Saving persons status to %s" % self.persons_btpresence_file)
        except IOError:
            self.logger.warning("Could not save persons status to file!")

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

    def always_at_home(self, args):
        if args[0] == "true":
            self.always_at_home = True
            self.logger.info("Presence always_at_home override ENABLED, sending presence status: "
                             "%s@%s" % (self.always_at_home, self.core.location))
            self.presence_event(self.users_here)
            return ["Always at home override ENABLED"]
        else:
            self.always_at_home = False
            self.logger.info("Presence always_at_home override DISABLED, sending presence status: "
                             "%s@%s" % (self.always_at_home, self.core.location))
            self.presence_event(self.users_here)
            return ["Always at home override DISABLED"]

    # ensure to send our presence info at least every self.core.config['presence_timeout']
    def presence_keepalive_daemon(self):
        self.presence_event(self.users_here)
        sleep = self.core.config['core']['presence_timeout'] + random.randint(-15, -5)
        self.core.add_timeout(sleep, self.presence_keepalive_daemon)

    # presence daemon methods
    def presence_check_daemon(self):
        self.presence_check(None)
        sleep = self.config['sleep_short'] + random.randint(-2, 2)
        if len(self.users_here):
            sleep = self.config['sleep_long'] + random.randint(-2, 2)
        self.logger.debug('Bluetooth presence scan sleeping for %s seconds' % sleep)
        self.current_presence_sleep = sleep
        self.core.add_timeout(sleep, self.presence_check_daemon)

    def presence_check(self, args):
        self.last_presence_check_start = time.time()
        self.worker_threads.append(self.core.spawn_subprocess(self.presence_check_worker,
                                                              self.presence_check_worker_callback,
                                                              None,
                                                              self.logger))

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

                        for line in clear_list:
                            if "bytes from" in line:
                                mac_addresses.append(mac)
            except KeyError:
                # person has no bt_devices
                pass
            except Exception:
                # probably parse error from command
                pass
        return mac_addresses

    def presence_check_worker_callback(self, mac_addresses):
        self.logger.debug('Presence scan finished, found <%s>' % ', '.join(mac_addresses))
        self.presence_checks += 1
        self.last_presence_check_end = time.time()
        self.last_presence_check_duration = self.last_presence_check_end - self.last_presence_check_start
        persons_detected = []

        # registering the person for which devices as detected
        for mac_address in mac_addresses:
            for person in list(self.core.config['persons'].keys()):
                if 'bt_devices' in self.core.config['persons'][person].keys():
                    for device in self.core.config['persons'][person]['bt_devices'].values():
                        if device.lower() == mac_address.lower():
                            persons_detected.append(person)

        persons_detected = sorted(list(set(persons_detected)))

        # if something changed, increment the presence_updates counter
        if self.tmp_users_here != persons_detected:
            self.presence_updates += 1
            if len(persons_detected):
                self.logger.info('Bluetooth presence: Now at <%s>: ' % self.core.location + ', '.join(persons_detected))
            else:
                self.logger.info('Bluetooth presence: Nobody is at <%s>' % self.core.location)

        persons_left = set(self.tmp_users_here).difference(persons_detected)
        persons_came = set(persons_detected).difference(self.tmp_users_here)

        message = []
        if persons_came:
            message.append(' and '.join(persons_came) + ' entered')
        if persons_left:
            message.append(' and '.join(persons_left) + ' left')

        # saving the actual persons detected
        self.tmp_users_here = persons_detected

        # use the missing-counter to be able to work around BT devices which not always answer ping
        if len(self.tmp_users_here) == 0:
            self.missing_count += 1
            if self.missing_count == 0:
                # this only happens on the very first run after startup to suppress the msg
                pass
            elif self.missing_count == int(self.config['miss_count']):
                message = list(set(self.messageCache))
                self.messageCache = []
                message.append('Bluetooth presence is starting to watch on %s for <%s>!' %
                               (self.core.hostname, self.core.location))
                self.logger.info("Bluetooth presence missing-counter reached its max (%s), sending presence status: "
                                 "%s@%s" % (self.config['miss_count'], self.users_here, self.core.location))
                self.users_here = self.tmp_users_here
                self.presence_event(self.users_here)
            elif self.missing_count < int(self.config['miss_count']):
                self.logger.info('Bluetooth presence missing-counter increased to %s of %s' %
                                 (self.missing_count, self.config['miss_count']))
                self.messageCache = self.messageCache + message
                message = []
            else:
                # since the count keeps counting, just ignore it
                pass

        if self.tmp_users_here != self.users_here and len(self.users_here):
            if self.missing_count >= int(self.config['miss_count']):
                message.append('Bluetooth presence is stopping to watch on %s for <%s>!' %
                               (self.core.hostname, self.core.location))
                self.presence_event(self.users_here)
            else:
                message = []
            # making sure, the missing counter is reset every time someone is around
            self.missing_count = 0

        if len(message):
            self.send_command(['jab', 'msg', ', '.join(message)])

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
        self.wait_for_threads(self.worker_threads)

    def return_status(self, verbose=False):
        ret = {'presence_checks': self.presence_checks, 'presence_updates': self.presence_updates,
               'alwaysAtHome': self.always_at_home, 'last_presence_check_start': self.last_presence_check_start,
               'last_presence_check_end': self.last_presence_check_end,
               'last_presence_check_duration': self.last_presence_check_duration,
               'current_presence_sleep': self.current_presence_sleep, 'current_presence_state': self.users_here,
               'nextCheckIn': self.last_presence_check_end + self.current_presence_sleep - time.time()}
        return ret


descriptor = {
    'name': 'btpresence',
    'help_text': 'Bluetooth presence detection plugin',
    'command': 'prox',
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
                     'last_presence_check_duration': "Last Proximity check duration"}
}
