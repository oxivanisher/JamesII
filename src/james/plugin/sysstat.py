
import sys
import time
import psutil
import datetime

from james.plugin import *

class SysstatPlugin(Plugin):

    def __init__(self, core):
        super(SysstatPlugin, self).__init__(core, SysstatPlugin.name)

        self.create_command('stat', self.cmd_sysstat, 'psutil system stats')

    def cmd_sysstat(self, args):
        sub_commands = {'mount' : self.sysstat_mount,
                        'uptime' : self.sysstat_uptime,
                        'net' : self.sysstat_net,
                        'who' : self.sysstat_who,
                        'cpu' : self.sysstat_cpu,
                        'mem' : self.sysstat_mem}

        output = ("subcommands are: %s" % (', '.join(sub_commands.keys())))
        try:
            user_command = args[0]
        except Exception as e:
            return (output)
        for command in sub_commands.keys():
            if command == user_command:
                return sub_commands[command](args[1:])
        return (output)        

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
    'mode' : PluginMode.AUTOLOAD,
    'class' : SysstatPlugin
}

