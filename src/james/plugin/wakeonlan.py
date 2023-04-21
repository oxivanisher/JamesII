import time

from james.plugin import *


class WakeOnLanPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(WakeOnLanPlugin, self).__init__(core, descriptor)

        self.core = core
        self.wol_devices = []
        for person in list(self.core.config['persons'].keys()):
            try:
                for name in list(self.core.config['persons'][person]['eth_devices'].keys()):
                    self.wol_devices.append((name, self.core.config['persons'][person]['eth_devices'][name], person))
            except KeyError:
                pass

        self.commands.create_subcommand('list', 'Lists available wol target hosts', self.wol_list)
        self.commands.create_subcommand('wake', 'Wakes up a given host (hostname)', self.wol_wake)

        self.load_state('wakeups', 0)

    def wol_list(self, args):
        ret = []
        for (name, mac, person) in self.wol_devices:
            ret.append("%-20s %-10s %s" % (mac, person, name))
        return ret

    def wol_wake(self, args):
        host = None
        try:
            for (name, mac, person) in self.wol_devices:
                if args[0] == name:
                    host = mac

        except Exception as e:
            return ["no valid hostname given"]

        if host:
            self.wakeups += 1
            self.utils.wake_on_lan(host)
            return ["waking %s (%s)" % (args[0], host)]

    def process_proximity_event(self, new_status):
        if (time.time() - self.core.startup_timestamp) > 10:
            if new_status['status'][self.core.location]:
                self.logger.debug("Processing proximity event")

                # finding out, which persons are home - sadly, this is currently NOT possible since only the proximity
                # node knows this
                # isHere = []
                # for person in self.core.persons_status.keys():
                #     self.logger.debug(new_status['status'][self.core.location])
                #     if self.core.persons_status[person]:
                #         isHere.append(person)
                # self.logger.debug("Persons detected here: %s" % (", ".join(isHere)))
                #     if person in isHere: ....

                ret = []
                for (name, mac, person) in self.wol_devices:
                    self.core.add_timeout(0, self.utils.wake_on_lan, str(mac))
                    ret.append('WOL Woke host %s (%s) for %s' % (name, mac, person))
                self.logger.info(ret)

    def return_status(self, verbose=False):
        ret = {'wakeups': self.wakeups}
        return ret


descriptor = {
    'name': 'wakeonlan',
    'help_text': 'Wake on lan plugin',
    'command': 'wol',
    'mode': PluginMode.MANAGED,
    'class': WakeOnLanPlugin,
    'detailsNames': {'wakeups': "Sent wakeups"}
}
