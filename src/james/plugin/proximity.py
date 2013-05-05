import sys
import os
import subprocess
import getpass
import time
import atexit
import json

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

        for person in self.core.config['persons'].keys():
            self.persons_status[person] = False

        atexit.register(self.save_state)
        self.persons_status_file = os.path.join(os.path.expanduser("~"), ".james_persons_status")
        self.proxy_send_lock = False
        self.load_saved_state()
        self.worker_threads = []

        self.proximityChecks = 0
        self.proximityUpdates = 0
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
            if self.core.config['persons'][person]['bt_devices']:
                for name in self.core.config['persons'][person]['bt_devices'].keys():
                    mac = self.core.config['persons'][person]['bt_devices'][name]
                    ret = self.utils.popenAndWait(['/usr/bin/hcitool', 'info', mac])
                    clear_list = filter(lambda s: s != '', ret)
                    try:
                        for line in clear_list:
                            if "Device Name:" in line:
                                args = line.split(':')
                                hosts.append((mac, args[1].strip()))
                    except Exception:
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
            self.status = True
        else:
            # compensating if the device is just for 1 aptempt not reachable
            if len(self.hosts_online) > 0:
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
                if self.core.config['persons'][person]['bt_devices']:
                    for device in self.core.config['persons'][person]['bt_devices'].values():
                        if device == mac:
                            persons_detected.append(person)
                            new_persons_status[person] = True

        # save the actual online hosts to var
        self.hosts_online = new_hosts_online

        # checking for newly detected persons
        for person in new_persons_status.keys():
            try:
                self.persons_status[person]
            except KeyError:
                # compensating for config changes
                self.persons_status[person] = False
            if new_persons_status[person] != self.persons_status[person]:
                message = self.core.new_message(self.name)
                message.level = 1
                if new_persons_status[person]:
                    message.header = ("%s is here" % person)
                else:
                    message.header = ("%s left" % person)
                message.body = ("Location: %s" % self.core.location)
                message.send()
        # saving the actual persons detected
        self.persons_status = new_persons_status

        if self.status != self.core.proximity_status.get_status_here():
            self.proximityUpdates += 1
            if self.status:
                self.logger.info('You are now at home')
            else:
                self.logger.info('You are now away')
            # self.core.proximity_status.set_status_here(self.status, 'btproximity')
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
                       'lastProximityCheckDuration' : "Last Proximity check duration" }
}
