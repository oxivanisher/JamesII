import sys
import os
import subprocess
import getpass
import time
import atexit
import json
import random
from bluetooth import *

from james.plugin import *


# FIXME add net scan with "arp-scan -I $NETINTERFACE -q --localnet | sort -t . -k 1,1n -k 2,2n -k 3,3n -k 4,4n"
# where do we keep the store of mac adresses? objects, objects, objects

class ProximityPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(ProximityPlugin, self).__init__(core, descriptor)

        self.status = False
        self.hosts_online = []
        self.persons_status = {}

        # check required tools
        self.tools = {'hcitool': '/usr/bin/hcitool',
                      'l2ping': '/usr/bin/l2ping',
                      'bluez-simple-agent': 'bluez-simple-agent'}

        for tool in self.tools.keys():
            if os.path.isfile(self.tools[tool]):
                self.logger.debug("%s found in %s" % (tool, self.tools[tool]))
            else:
                self.logger.warning("%s NOT found in %s" % (tool, self.tools[tool]))

        if os.path.isfile(self.tools['hcitool']):
            # self.commands.create_subcommand('discover', 'Scan for visible bluetooth devices', self.discover)
            self.commands.create_subcommand('test', 'Test for local bluetooth devices', self.test)
            if self.core.os_username == 'root':
                self.commands.create_subcommand('persons', 'Shows the persons currently detected', self.show_persons)
                self.commands.create_subcommand('proximity', 'Run a manual proximity check', self.proximity_check)
                self.commands.create_subcommand('pair', 'Pair with a device (add BT MAC)', self.prepare_pair)
                self.commands.create_subcommand('always_at_home', 'Override to be always at home (true/false)',
                                                self.always_at_home)
                self.commands.create_subcommand('show', 'Show detailed information on states', self.show_details)

        for person in self.core.config['persons'].keys():
            self.persons_status[person] = False

        atexit.register(self.save_state)
        self.persons_status_file = os.path.join(os.path.expanduser("~"), ".james_persons_status")
        self.proxy_send_lock = False
        self.load_saved_state()

        self.load_state('proximityChecks', 0)
        self.load_state('proximityUpdates', 0)
        self.load_state('alwaysAtHome', False)
        self.lastProximityCheckStart = 0
        self.lastProximityCheckEnd = 0
        self.lastProximityCheckDuration = 0
        self.currentProximitySleep = 0
        self.missing_count = -1
        self.messageCache = []

    def start(self):
        if self.core.os_username == 'root':
            # wait 3 seconds before working
            self.core.add_timeout(0, self.proximity_check_daemon)

        # publish the initial override state
        self.core.proximity_event(self.alwaysAtHome, 'override')

        # publish the btproximity state (core only publishes something, if it has changed.
        # so loading the state from file should be save.)
        self.core.proximity_event(self.status, 'btproximity', True)

    def load_saved_state(self):
        try:
            # load saved proximity persons
            self.logger.debug("Loading persons status from %s" % self.persons_status_file)
            proximity_file = open(self.persons_status_file, 'r')
            self.persons_status = json.loads(proximity_file.read())
            proximity_file.close()

            # read saved location proximity from core (which comes from the saved file)
            self.logger.debug("Reading and using local proximity state from core")
            self.status = self.core.proximity_status.status[self.core.location]

        except IOError:
            pass
        pass

    def save_state(self):
        try:
            file_handler = open(self.persons_status_file, 'w')
            file_handler.write(json.dumps(self.persons_status))
            file_handler.close()
            self.logger.debug("Saving persons status to %s" % self.persons_status_file)
        except IOError:
            self.logger.warning("Could not save persons status to file!")

    # command methods
    def test(self, args):
        devices = {}
        lines = self.utils.popenAndWait([self.tools['hcitool'], 'dev'])
        lines = self.utils.list_unicode_cleanup(lines)
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                devices[values[1]] = values[0]
        return devices

    def prepare_pair(self, args):
        key = random.randint(1000, 9999)
        pairMsg = "Bluetooth pairing key is: %s" % key
        lines = self.utils.popenAndWait([self.tools['bluez-simple-agent'], 'hci0', args[0], 'remove'])
        pairData = [args[0], key]
        self.core.add_timeout(0, self.pair, pairData)
        return pairMsg

    def pair(self, pair_data):
        p = subprocess.Popen([self.tools['bluez-simple-agent'],
                              'hci0', pair_data[0]],
                             stdout=subprocess.PIPE,
                             stdin=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        pair_out = p.communicate(input=str(pair_data[1]) + '\n')[0]
        self.logger.debug("BT Logging output: %s" % pair_out)

    # def discover(self, args):
    #     self.logger.debug('Discovering bluetooth hosts...')
    #
    #     nearby_devices = discover_devices(lookup_names=True)
    #     hosts = {}
    #     if len(nearby_devices):
    #         for name, addr in nearby_devices:
    #             hosts[addr] = name
    #     self.logger.debug('Found %s bluetooth hosts' % len(nearby_devices))
    #     return hosts

    def show_persons(self, args):
        ret = []
        for person in self.persons_status.keys():
            if self.persons_status[person]:
                ret.append("%10s is here" % person)
            else:
                ret.append("%10s is not here" % person)
        return ret

    def show_details(self, args):
        return self.core.proximity_status.details()

    def always_at_home(self, args):
        if args[0] == "true":
            self.alwaysAtHome = True
            self.logger.info("Proximity always_at_home override ENABLED, sending proximity status: "
                             "%s@%s" % (self.alwaysAtHome, self.core.location))
            self.core.proximity_event(True, 'override')
            return ["Always at home override ENABLED"]
        else:
            self.alwaysAtHome = False
            self.logger.info("Proximity always_at_home override DISABLED, sending proximity status: "
                             "%s@%s" % (self.alwaysAtHome, self.core.location))
            self.core.proximity_event(False, 'override')
            return ["Always at home override DISABLED"]

    # proximity daemon methods
    def proximity_check_daemon(self):
        self.proximity_check(None)
        sleep = self.config['sleep_short'] + random.randint(-2, 2)
        if self.status:
            sleep = self.config['sleep_long'] + random.randint(-2, 2)
        self.logger.debug('Bluetooth proximity scan sleeping for %s seconds' % sleep)
        self.currentProximitySleep = sleep
        self.core.add_timeout(sleep, self.proximity_check_daemon)

    def proximity_check(self, args):
        self.lastProximityCheckStart = time.time()
        self.worker_threads.append(self.core.spawnSubprocess(self.proximity_check_worker,
                                                             self.proximity_check_callback,
                                                             None,
                                                             self.logger))

    def proximity_check_worker(self):
        self.logger.debug('Starting bluetooth proximity scan for <%s>' % self.core.location)
        hosts = []
        for person in self.core.config['persons'].keys():
            try:
                if self.core.config['persons'][person]['bt_devices']:
                    for name in self.core.config['persons'][person]['bt_devices'].keys():
                        mac = self.core.config['persons'][person]['bt_devices'][name]
                        ret = self.utils.popenAndWait([self.tools['l2ping'], '-c', '1', mac])
                        clear_list = filter(lambda s: s != '', ret)

                        for line in clear_list:
                            if "bytes from" in line:
                                hosts.append((mac, mac))
            except KeyError:
                # person has no bt_devices
                pass
            except Exception:
                # probably parse error from command
                pass
        return hosts

    def proximity_check_callback(self, values):
        self.logger.debug('Proximity scan finished')
        self.proximityChecks += 1
        self.lastProximityCheckEnd = time.time()
        self.lastProximityCheckDuration = self.lastProximityCheckEnd - self.lastProximityCheckStart
        oldstatus = self.status
        self.status = False  # True means that someone is around
        old_hosts_online = self.hosts_online
        new_hosts_online = []
        persons_detected = []
        new_persons_status = {}

        # resetting persons detected
        for person in self.core.config['persons'].keys():
            new_persons_status[person] = False

        if len(values) > 0:
            self.logger.debug("Setting self.status to True because devices where detected")
            self.status = True

        for (mac, name) in values:
            notfound = True
            new_hosts_online.append((mac, name))
            for (test_mac, test_name) in old_hosts_online:
                if test_mac.lower() == mac.lower():
                    notfound = False
            if notfound:
                self.logger.info('Bluetooth proximity found %s at <%s>' % (name, self.core.location))

        for (mac, name) in old_hosts_online:
            notfound = True
            for (test_mac, test_name) in new_hosts_online:
                if test_mac.lower() == mac.lower():
                    notfound = False
            if notfound:
                self.logger.info('Bluetooth proximity lost %s at <%s>' % (name, self.core.location))

        # registering the person for these devices as detected
        for (mac, name) in values:
            for person in self.core.config['persons'].keys():
                try:
                    if self.core.config['persons'][person]['bt_devices']:
                        for device in self.core.config['persons'][person]['bt_devices'].values():
                            if device.lower() == mac.lower():
                                persons_detected.append(person)
                                new_persons_status[person] = True
                except KeyError:
                    pass

        # save the actual online hosts to var
        self.hosts_online = new_hosts_online

        # if something changed, increment the proximityUpdates counter
        if self.status != self.core.proximity_status.get_status_here():
            self.proximityUpdates += 1

        # checking for newly detected persons
        personsChanged = False
        personsLeft = []
        personsCame = []
        for person in new_persons_status.keys():
            try:
                self.persons_status[person]
            except KeyError:
                # compensating for config changes
                self.persons_status[person] = False
            if new_persons_status[person] != self.persons_status[person]:
                personsChanged = True
                if new_persons_status[person]:
                    personsCame.append(person)
                else:
                    personsLeft.append(person)

        self.core.send_persons_status(new_persons_status, 'btproximity')
        if personsChanged:
            if self.status:
                isHere = []
                for person in new_persons_status:
                    if new_persons_status[person]:
                        isHere.append(person)
                self.logger.info('Bluetooth proximity: Now at <%s>: ' % self.core.location + ', '.join(isHere))
            else:
                self.logger.info('Bluetooth proximity: Nobody is at <%s>' % self.core.location)

        message = []
        if personsCame:
            message.append(' and '.join(personsCame) + ' entered')
        if personsLeft:
            message.append(' and '.join(personsLeft) + ' left')

        # saving the actual persons detected
        self.persons_status = new_persons_status

        # use the missingcounter to be able to work around BT devices which not always answer ping
        if not self.status:
            self.missing_count += 1
            if self.missing_count == 0:
                # this only happens on the very first run after startup to suppress the message
                pass
            elif self.missing_count == int(self.config['miss_count']):
                message = list(set(self.messageCache))
                self.messageCache = []
                message.append('Bluetooth proximity is starting to watch on %s for <%s>!' %
                               (self.core.hostname, self.core.location))
                self.logger.info("Bluetooth proximity missingcounter reached its max (%s), sending proximity status: "
                                 "%s@%s" % (self.config['miss_count'], self.status, self.core.location))
                self.core.proximity_event(self.status, 'btproximity')
            elif self.missing_count < int(self.config['miss_count']):
                self.logger.info('Bluetooth proximity missingcounter increased to %s of %s' %
                                 (self.missing_count, self.config['miss_count']))
                self.messageCache = self.messageCache + message
                message = []
            else:
                # since the count keeps counting, just ignore it
                pass

        if oldstatus != self.status and self.status:
            if self.missing_count >= int(self.config['miss_count']):
                message.append('Bluetooth proximity is stopping to watch on %s for <%s>!' %
                               (self.core.hostname, self.core.location))
                self.core.proximity_event(self.status, 'btproximity')
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
        self.logger.debug('Publishing bluetooth proximity event')
        self.proxy_send_lock = False
        self.core.publish_proximity_status({self.core.location: self.core.proximity_status.get_status_here()},
                                           'btproximity')

    def terminate(self):
        self.wait_for_threads(self.worker_threads)

    def return_status(self, verbose=False):
        ret = {}
        ret['proximityChecks'] = self.proximityChecks
        ret['proximityUpdates'] = self.proximityUpdates
        ret['alwaysAtHome'] = self.alwaysAtHome
        ret['lastProximityCheckStart'] = self.lastProximityCheckStart
        ret['lastProximityCheckEnd'] = self.lastProximityCheckEnd
        ret['lastProximityCheckDuration'] = self.lastProximityCheckDuration
        ret['currentProximitySleep'] = self.currentProximitySleep
        ret['currentProximityState'] = self.status
        ret['nextCheckIn'] = self.lastProximityCheckEnd + self.currentProximitySleep - time.time()
        return ret


descriptor = {
    'name': 'proximity',
    'help': 'Proximity detection plugin',
    'command': 'prox',
    'mode': PluginMode.MANAGED,
    'class': ProximityPlugin,
    'detailsNames': {'proximityChecks': "Run proximity checks",
                     'proximityUpdates': "Proximity status changes",
                     'alwaysAtHome': "Always at home override active",
                     'lastProximityCheckStart': "Last Proximity check start",
                     'lastProximityCheckEnd': "Last Proximity check end",
                     'currentProximitySleep': "Current sleep time",
                     'currentProximityState': "Current proximity state",
                     'nextCheckIn': "Next check in",
                     'lastProximityCheckDuration': "Last Proximity check duration"}
}
