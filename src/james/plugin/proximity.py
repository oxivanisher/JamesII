import sys
import os
import subprocess
import getpass
import time
import atexit
import json

from james.plugin import *

class ProximityPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(ProximityPlugin, self).__init__(core, descriptor)

        self.status = False
        self.hosts_online = []
        self.persons_status = {}

        self.commands.create_subcommand('persons', 'shows the persons currently detected', self.show_persons)
        if os.path.isfile('/usr/bin/hcitool'):
            self.commands.create_subcommand('discover', 'scan for visible bluetooth devices', self.discover)
            self.commands.create_subcommand('test', 'test for local bluetooth devices', self.test)
            if core.os_username == 'root':
                self.commands.create_subcommand('proximity', 'run a manual proximity check', self.proximity_check)
                self.core.add_timeout(1, self.proximity_check_daemon)

        for person in self.core.config['persons'].keys():
            self.persons_status[person] = False

        atexit.register(self.save_state)
        self.state_file = os.path.join(os.path.expanduser("~"), ".james_proximity_state")
        self.persons_status_file = os.path.join(os.path.expanduser("~"), ".james_persons_status")
        self.proxy_send_lock = False
        self.load_saved_state()

    def load_saved_state(self):
        try:
            file = open(self.state_file, 'r')
            loaded_status = self.core.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
            if self.core.config['core']['debug']:
                print("Loading proximity status from %s" % (self.state_file))
            # force proximity update
            if self.status:
                self.core.proximity_status.status[self.core.location] = False
            else:
                self.core.proximity_status.status[self.core.location] = True
            self.core.proximity_event(loaded_status, 'btproximity')
        except IOError:
            pass
        pass

        try:
            file = open(self.persons_status_file, 'r')
            self.persons_status = self.core.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
            if self.core.config['core']['debug']:
                print("Loading persons status from %s" % (self.persons_status_file))
        except IOError:
            pass
        pass


    def save_state(self):
        try:
            file = open(self.state_file, 'w')
            file.write(json.dumps(self.status))
            file.close()
            if self.core.config['core']['debug']:
                print("Saving proximity status to %s" % (self.state_file))
        except IOError:
            print("WARNING: Could not safe proximity status to file!")

        try:
            file = open(self.persons_status_file, 'w')
            file.write(json.dumps(self.persons_status))
            file.close()
            if self.core.config['core']['debug']:
                print("Saving persons status to %s" % (self.persons_status_file))
        except IOError:
            print("WARNING: Could not safe persons status to file!")

    # command methods
    def test(self, args):
        devices = {}
        lines = self.core.utils.popenAndWait(['hcitool', 'dev'])
        lines = self.core.utils.list_unicode_cleanup(lines)
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                devices[values[1]] = values[0]
        return(devices)

    def discover(self, args):
        lines = self.core.utils.popenAndWait(['hcitool', 'scan'])
        lines = self.core.utils.list_unicode_cleanup(lines)
        hosts = {}
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                hosts[values[0]] = values[1]
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
        sleep = self.core.config['proximity']['sleep_short']
        if self.status:
            sleep = self.core.config['proximity']['sleep_long']
        self.core.add_timeout(sleep, self.proximity_check_daemon)

    def proximity_check(self, args):
        self.core.spawnSubprocess(self.proximity_check_worker,
                                  self.proximity_check_callback)

    def proximity_check_worker(self):
        hosts = []
        for person in self.core.config['persons'].keys():
            for name in self.core.config['persons'][person]['bt_devices'].keys():
                mac = self.core.config['persons'][person]['bt_devices'][name]
                ret = self.core.utils.popenAndWait(['/usr/bin/hcitool', 'info', mac])
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
                self.send_response(self.uuid, 'broadcast', (['Proximity found %s' % (name)]))

        for (mac, name) in old_hosts_online:
            notfound = True
            for (test_mac, test_name) in new_hosts_online:
                if test_mac == mac:
                    notfound = False
            if notfound:
                self.send_response(self.uuid, 'broadcast', (['Proximity lost %s' % (name)]))

        # registering the person for this device as detected
        for (mac, name) in values:
            for person in self.core.config['persons'].keys():
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
                    message.header = ("%s is now here" % person)
                else:
                    message.header = ("%s left" % person)
                message.body = ("Location: %s" % self.core.location)
                # message.send()
        # saving the actual persons detected
        self.persons_status = new_persons_status

        if self.status != self.oldstatus:
            if self.status:
                self.send_response(self.uuid, 'broadcast', ['You are now at home'])
            else:
                self.send_response(self.uuid, 'broadcast', ['You are now away'])
            self.core.proximity_status.set_status_here(self.status, 'btproximity')

    def process_discovery_event(self, msg):
        if not self.proxy_send_lock:
            if msg[0] == 'hello':
                self.proxy_send_lock = True
                self.core.add_timeout(5, self.process_discovery_event_callback)

    def process_discovery_event_callback(self):
        self.core.publish_proximity_status({ self.core.location : self.core.proximity_status.get_status_here() }, 'btproximity')
        self.proxy_send_lock = False

descriptor = {
    'name' : 'proximity',
    'help' : 'proximity with bluetooth',
    'command' : 'prox',
    'mode' : PluginMode.MANAGED,
    'class' : ProximityPlugin
}
