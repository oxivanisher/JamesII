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

        if os.path.isfile('/usr/bin/hcitool'):
            self.commands.create_subcommand('scan', 'scan for visible bluetooth devices', self.scan)
            self.commands.create_subcommand('test', 'test for local bluetooth devices', self.test)
            if core.os_username == 'root':
                self.commands.create_subcommand('proximity', 'run a manual proximity check', self.proximity_check)
                self.proximity_check_daemon()

        atexit.register(self.save_state)
        self.state_file = os.path.join(os.path.expanduser("~"), ".james_proximity_state")
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

    def save_state(self):
        try:
            file = open(self.state_file, 'w')
            file.write(json.dumps(self.status))
            file.close()
            if self.core.config['core']['debug']:
                print("Saving proximity status to %s" % (self.state_file))
        except IOError:
            print("WARNING: Could not safe cached commands to file!")

    def test(self, args):
        devices = {}
        lines = self.core.utils.popenAndWait(['hcitool', 'dev'])
        lines = self.core.utils.list_unicode_cleanup(lines)
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                devices[values[1]] = values[0]
        return(devices)

    def scan(self, args):
        lines = self.core.utils.popenAndWait(['hcitool', 'scan'])
        lines = self.core.utils.list_unicode_cleanup(lines)
        hosts = {}
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                hosts[values[0]] = values[1]
        return(hosts)

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
            for name in self.core.config['persons'][person]['devices'].keys():
                mac = self.core.config['persons'][person]['devices'][name]
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
                self.send_response(self.uuid, 'broadcast', ('Proximity found %s' % (name)))

        for (mac, name) in old_hosts_online:
            notfound = True
            for (test_mac, test_name) in new_hosts_online:
                if test_mac == mac:
                    notfound = False
            if notfound:
                self.send_response(self.uuid, 'broadcast', ('Proximity lost %s' % (name)))

        # save the actual online hosts to var
        self.hosts_online = new_hosts_online

        if self.status != self.oldstatus:
            if self.status:
                self.send_response(self.uuid, 'broadcast', 'You are now at home')
            else:
                self.send_response(self.uuid, 'broadcast', 'You are now away')

            self.core.proximity_status.set_status_here(self.status, 'btproximity')

descriptor = {
    'name' : 'proximity',
    'help' : 'proximity with bluetooth',
    'command' : 'prox',
    'mode' : PluginMode.MANAGED,
    'class' : ProximityPlugin
}
