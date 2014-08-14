import sys
import os
import subprocess
import getpass
import time
import atexit
import json
import random

from james.plugin import *

# FIXME add net scan with "arp-scan -I $NETINTERFACE -q --localnet | sort -t . -k 1,1n -k 2,2n -k 3,3n -k 4,4n"
# where do we keep the store of mac adresses? objects, objects, objects

class ProximityPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(ProximityPlugin, self).__init__(core, descriptor)

        self.status = False
        self.hosts_online = []
        self.persons_status = {}

        if os.path.isfile('/usr/bin/hcitool'):
            self.commands.create_subcommand('discover', 'Scan for visible bluetooth devices', self.discover)
            self.commands.create_subcommand('test', 'Test for local bluetooth devices', self.test)
            if self.core.os_username == 'root':
                self.commands.create_subcommand('persons', 'Shows the persons currently detected', self.show_persons)
                self.commands.create_subcommand('proximity', 'Run a manual proximity check', self.proximity_check)
                self.commands.create_subcommand('pair', 'Pair with a device (add BT MAC)', self.prepair_pair)

        for person in self.core.config['persons'].keys():
            self.persons_status[person] = False

        atexit.register(self.save_state)
        self.persons_status_file = os.path.join(os.path.expanduser("~"), ".james_persons_status")
        self.proxy_send_lock = False
        self.load_saved_state()

        self.load_state('proximityChecks', 0)
        self.load_state('proximityUpdates', 0)
        self.lastProximityCheckStart = 0
        self.lastProximityCheckEnd = 0
        self.lastProximityCheckDuration = 0
        self.currentProximitySleep = 0

    def start(self):
        if self.core.os_username == 'root':
            # wait 3 seconds befor working
            self.core.add_timeout(0, self.proximity_check_daemon)

    def load_saved_state(self):
        try:
            file = open(self.persons_status_file, 'r')
            # self.persons_status = self.utils.convert_from_unicode(json.loads(file.read()))
            self.persons_status = json.loads(file.read())
            file.close()
            self.logger.debug("Loading persons status from %s" % (self.persons_status_file))
        except IOError:
            pass
        pass

    def save_state(self):
        try:
            file = open(self.persons_status_file, 'w')
            file.write(json.dumps(self.persons_status))
            file.close()
            self.logger.debug("Saving persons status to %s" % (self.persons_status_file))
        except IOError:
            self.logger.warning("Could not save persons status to file!")

    # command methods
    def test(self, args):
        devices = {}
        lines = self.utils.popenAndWait(['hcitool', 'dev'])
        lines = self.utils.list_unicode_cleanup(lines)
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                devices[values[1]] = values[0]
        return(devices)

    def prepair_pair(self, args):
        key = random.randint(1000,9999)
        pairMsg = "Bluetooth pairing key is: %s" % key
        lines = self.utils.popenAndWait(['bluez-simple-agent', 'hci0', args[0], 'remove'])
        pairData = [args[0], key]
        self.core.add_timeout(0, self.pair, pairData)
        return pairMsg

    def pair(self, pairData):
        p = subprocess.Popen(['bluez-simple-agent', 'hci0', pairData[0]], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
        pair_out = p.communicate(input=str(pairData[1]) + '\n')[0]
        self.logger.debug("BT Logging output: %s" % pair_out)

    def discover(self, args):
        self.logger.debug('Discovering bluetooth hosts...')
        lines = self.utils.popenAndWait(['hcitool', 'scan'])
        lines = self.utils.list_unicode_cleanup(lines)
        hosts = {}
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                hosts[values[0]] = values[1]
        self.logger.debug('Found %s bluetooth hosts' % len(hosts))
        return(hosts)

    def show_persons(self, args):
        ret = []
        for person in self.persons_status.keys():
            if self.persons_status[person]:
                ret.append("%10s is here" % (person))
            else:
                ret.append("%10s is not here" % (person))
        return ret

    # proximity daemon methods
    def proximity_check_daemon(self):
        self.proximity_check(None)
        sleep = self.config['sleep_short']
        if self.status:
            sleep = self.config['sleep_long']
        self.logger.debug('Proximity scan sleeping for %s seconds' % sleep)
        self.currentProximitySleep = sleep
        self.core.add_timeout(sleep, self.proximity_check_daemon)

    def proximity_check(self, args):
        self.lastProximityCheckStart = time.time()
        self.worker_threads.append(self.core.spawnSubprocess(self.proximity_check_worker,
                                  self.proximity_check_callback,
                                  None,
                                  self.logger))

    def proximity_check_worker(self):
        self.logger.debug('Starting proximity scan')
        hosts = []
        for person in self.core.config['persons'].keys():
            try:
                if self.core.config['persons'][person]['bt_devices']:
                    for name in self.core.config['persons'][person]['bt_devices'].keys():
                        mac = self.core.config['persons'][person]['bt_devices'][name]
                        ret = self.utils.popenAndWait(['/usr/bin/hcitool', 'info', mac])
                        clear_list = filter(lambda s: s != '', ret)

                        for line in clear_list:
                            if "Device Name:" in line:
                                args = line.split(':')
                                hosts.append((mac, args[1].strip()))
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
        self.oldstatus = self.status
        self.status = False
        old_hosts_online = self.hosts_online
        new_hosts_online = []
        persons_detected = []
        new_persons_status = {}

        # resetting persons detected
        for person in self.core.config['persons'].keys():
            new_persons_status[person] = False

        if len(values) > 0:
            self.logger.debug("Setting self.status to True (phase 1)")
            self.status = True
        else:
            # compensating if the device is just for 1 aptempt not reachable
            if len(old_hosts_online) > 0:
                self.logger.debug("Setting self.status to True (phase 2)")
                self.status = True

        for (mac, name) in values:
            notfound = True
            new_hosts_online.append((mac, name))
            for (test_mac, test_name) in old_hosts_online:
                if test_mac == mac:
                    notfound = False
            if notfound:
                self.logger.info('Proximity found %s' % (name))

        for (mac, name) in old_hosts_online:
            notfound = True
            for (test_mac, test_name) in new_hosts_online:
                if test_mac == mac:
                    notfound = False
            if notfound:
                self.logger.info('Proximity lost %s' % (name))

        # registering the person for this device as detected
        for (mac, name) in values:
            for person in self.core.config['persons'].keys():
                try:
                    if self.core.config['persons'][person]['bt_devices']:
                        for device in self.core.config['persons'][person]['bt_devices'].values():
                            if device == mac:
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
                self.logger.info('Now at home: ' + ', '.join(isHere))
            else:
                self.logger.info('Nobody is at home')

        message = []
        if personsCame:
            message.append(' and '.join(personsCame) + ' entered')
        if personsLeft:
            message.append(' and '.join(personsLeft) + ' left')
        if len(message):
            self.send_command(['sys', 'alert', ', '.join(message)])

        # saving the actual persons detected
        self.persons_status = new_persons_status

        if personsChanged:
            self.logger.info("Persons changed, sending proximity status: %s@%s" % (self.status, self.core.location))
            self.core.proximity_event(self.status, 'btproximity')

    def process_discovery_event(self, msg):
        if not self.proxy_send_lock:
            if msg[0] == 'hello':
                self.proxy_send_lock = True
                self.core.add_timeout(3, self.process_discovery_event_callback)

    def process_discovery_event_callback(self):
        self.logger.debug('Publishing proximity event')
        self.proxy_send_lock = False
        self.core.publish_proximity_status({ self.core.location : self.core.proximity_status.get_status_here() }, 'btproximity')

    def terminate(self):
        self.wait_for_threads(self.worker_threads)

    def return_status(self):
        ret = {}
        ret['proximityChecks'] = self.proximityChecks
        ret['proximityUpdates'] = self.proximityUpdates
        ret['lastProximityCheckStart'] = self.lastProximityCheckStart
        ret['lastProximityCheckEnd'] = self.lastProximityCheckEnd
        ret['lastProximityCheckDuration'] = self.lastProximityCheckDuration
        ret['currentProximitySleep'] = self.currentProximitySleep
        ret['currentProximityState'] = self.status
        ret['nextCheckIn'] = self.lastProximityCheckEnd + self.currentProximitySleep - time.time()
        return ret

descriptor = {
    'name' : 'proximity',
    'help' : 'Proximity detection plugin',
    'command' : 'prox',
    'mode' : PluginMode.MANAGED,
    'class' : ProximityPlugin,
    'detailsNames' : { 'proximityChecks' : "Run proximity checks",
                       'proximityUpdates' : "Proximity status changes",
                       'lastProximityCheckStart' : "Last Proximity check start",
                       'lastProximityCheckEnd' : "Last Proximity check end",
                       'currentProximitySleep' : "Current sleep time",
                       'currentProximityState' : "Current proximity state",
                       'nextCheckIn' : "Next check in",
                       'lastProximityCheckDuration' : "Last Proximity check duration" }
}
