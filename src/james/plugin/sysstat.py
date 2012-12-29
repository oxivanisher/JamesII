
import sys
import time
import psutil
import datetime

from james.plugin import *

class SysstatPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(SysstatPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('cpu', 'Show the current cpu usage for all cores', self.sysstat_cpu)
        self.commands.create_subcommand('mount', 'Show mounted disks and the usage', self.sysstat_mount)
        self.commands.create_subcommand('mem', 'Show the free and used memory and swap', self.sysstat_mem)
        self.commands.create_subcommand('net', 'Show the network interfaces and their stats', self.sysstat_net)
        self.commands.create_subcommand('uptime', 'Show the system uptime', self.sysstat_uptime)
        self.commands.create_subcommand('who', 'Show logged in users', self.sysstat_who)

    def sysstat_mount(self, args):
        partitions = psutil.disk_partitions()
        return_str = []
        for partition in partitions:
            usage = psutil.disk_usage(partition.mountpoint)
            return_str.append("%s on %s as %s has %s%% used and %s free." % \
                    (partition.device, partition.mountpoint, partition.fstype, usage.percent, usage.free))
        return return_str

    def sysstat_uptime(self, args):
        return 'The System started %s, JamesII %s.' % \
                (self.core.utils.get_nice_age(int(round(psutil.BOOT_TIME, 0))), 
                self.core.utils.get_nice_age(int(round(self.core.startup_timestamp, 0))))

    def sysstat_net(self, args):
        interfaces = psutil.network_io_counters(pernic=True)
        return_str = []
        for interface in interfaces:
            if interface != "lo":
                netif = interfaces[interface]
                return_str.append("%-5s Sent: %-8s Recv: %-8s" % \
                                    (interface, 
                                    self.core.utils.bytes2human(netif.bytes_sent),
                                    self.core.utils.bytes2human(netif.bytes_recv)))
        return return_str

    def sysstat_who(self, args):
        users = psutil.get_users()
        return_str = []
        for user in users:
            return_str.append("%-15s %-15s %s (%s)" % \
                                (user.name,
                                user.terminal or '-',
                                self.core.utils.get_short_age(user.started),
                                #datetime.datetime.fromtimestamp(user.started).strftime("%Y-%m-%d %H:%M"),
                                user.host)
            )
        return return_str

    def sysstat_cpu(self, args):
        return_str = []
        total = float()
        ret_str = ""
        cpus = psutil.cpu_percent(interval=1, percpu=True)
        for cpu in cpus:
            total += cpu
            ret_str += "%4s%%" % (int(cpu))
        return_str.append("load avg %3s%%; threads %s" % (int(total / psutil.NUM_CPUS), ret_str))
        return return_str

    def sysstat_mem(self, args):
        mem_avail = True
        try:
            mem = psutil.virtual_memory()
        except AttributeError as e:
            mem_avail = False

        swap_avail = True
        try:
            swap = psutil.swap_memory()
        except AttributeError as e:
            swap_avail = False
        

        return_str = []

        if mem_avail:
            return_str.append("memory used %s/%s %s%%; avail %s; free %s" % \
                                (self.core.utils.bytes2human(mem.used),
                                self.core.utils.bytes2human(mem.total),
                                mem.percent,
                                self.core.utils.bytes2human(mem.available),
                                self.core.utils.bytes2human(mem.free)))

        if swap_avail:
            return_str.append("swap used %s/%s %s%%; free %s" % \
                                (self.core.utils.bytes2human(swap.used),
                                self.core.utils.bytes2human(swap.total),
                                swap.percent,
                                self.core.utils.bytes2human(swap.free)))

        return return_str

descriptor = {
    'name' : 'sysstat',
    'help' : 'Psutil system information',
    'command' : 'stat',
    'mode' : PluginMode.AUTOLOAD,
    'class' : SysstatPlugin
}

