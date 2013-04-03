
import sys
import time

from james.plugin import *

class WakeOnLanPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(WakeOnLanPlugin, self).__init__(core, descriptor)

        self.core = core
        self.wol_devices = []
        for person in self.core.config['persons'].keys():
            for name in self.core.config['persons'][person]['eth_devices'].keys():
                self.wol_devices.append((name, self.core.config['persons'][person]['eth_devices'][name]))

        self.commands.create_subcommand('list', 'Lists available wol target hosts', self.wol_list)
        self.commands.create_subcommand('wake', 'Wakes up a given host (hostname)', self.wol_wake)

    def wol_list(self, args):
        ret = []
        for (name, mac) in self.wol_devices:
            ret.append("%-20s %s" % (mac, name))
        return ret

    def wol_wake(self, args):
        host = None
        try:
            for (name, mac) in self.wol_devices:
                if args[0] == name:
                    host = mac

        except Exception as e:
            return "no valid hostname given"

        if host:
            self.core.utils.wake_on_lan(host)
            return (["waking %s (%s)" % (args[0], host)])

    def process_proximity_event(self, newstatus):
        if (time.time() - self.core.startup_timestamp) > 10:
            if newstatus['status'][self.core.location]:
                self.logger.debug("Processing proximity event")
                ret = []
                for (name, mac) in self.wol_devices:
                    self.core.utils.wake_on_lan(mac)
                    ret.append('WOL Woke host %s (%s)' % (name, mac))
                self.logger.info(ret)

descriptor = {
    'name' : 'wakeonlan',
    'help' : 'Wake on lan plugin',
    'command' : 'wol',
    'mode' : PluginMode.MANAGED,
    'class' : WakeOnLanPlugin
}

