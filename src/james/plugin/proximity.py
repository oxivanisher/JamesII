import sys
import os
import subprocess
import getpass
import time

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

    def terminate(self):
        # FIXME save out actual state to file?
        pass

    def test(self, args):
        devices = {}
        lines = self.core.utils.popenAndWait(['hcitool', 'dev'])
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                devices[values[1]] = values[0]
        return(devices)

    def scan(self, args):
        lines = self.core.utils.popenAndWait(['hcitool', 'scan'])
        hosts = {}
        if len(lines) > 1:
            for line in lines[1:]:
                values = line.split()
                hosts[values[0]] = values[1]
        if len(hosts) > 0:
            return(hosts)
        else:
            return("bluetooth scan: no devices found")

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
                if len(filter(lambda s: s != '', ret)) > 1:
                    hosts.append(mac)
        return hosts

    def proximity_check_callback(self, values):
        # FIXME we should consider, that the device may loose 1 connection attempt due RL
        self.oldstatus = self.status
        self.status = False

        if len(values) > 0:
            self.status = True

        self.hosts_online = self.core.utils.convert_from_unicode(values)

        if self.status != self.oldstatus:
            self.core.proximity_status.set_status_here(self.status, 'btproximity')

descriptor = {
    'name' : 'proximity',
    'help' : 'proximity with bluetooth',
    'command' : 'prox',
    'mode' : PluginMode.MANAGED,
    'class' : ProximityPlugin
}
