
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
        return (['The System started %s, JamesII %s.' % \
                (self.utils.get_nice_age(int(round(psutil.BOOT_TIME, 0))), 
                self.utils.get_nice_age(int(round(self.core.startup_timestamp, 0))))])

    def sysstat_net(self, args):
        interfaces = psutil.network_io_counters(pernic=True)
        return_str = []
        for interface in interfaces:
            if interface != "lo":
                netif = interfaces[interface]
                return_str.append("%-5s Sent: %-8s Recv: %-8s" % \
                                    (interface, 
                                    self.utils.bytes2human(netif.bytes_sent),
                                    self.utils.bytes2human(netif.bytes_recv)))
        return return_str

    def sysstat_who(self, args):
        users = psutil.get_users()
        return_str = []
        for user in users:
            return_str.append("%-15s %-15s %s (%s)" % \
                                (user.name,
                                user.terminal or '-',
                                self.utils.get_short_age(user.started),
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
        data = self.get_sysstat_mem()

        return_str = []

        if data['mem_avail']:
            return_str.append("memory used %s/%s %s%%; avail %s; free %s" % \
                                (self.utils.bytes2human(data['mem'].used),
                                self.utils.bytes2human(data['mem'].total),
                                data['mem'].percent,
                                self.utils.bytes2human(data['mem'].available),
                                self.utils.bytes2human(data['mem'].free)))

        if data['swap_avail']:
            return_str.append("swap used %s/%s %s%%; free %s" % \
                                (self.utils.bytes2human(data['swap'].used),
                                self.utils.bytes2human(data['swap'].total),
                                data['swap'].percent,
                                self.utils.bytes2human(data['swap'].free)))

        return return_str

    def get_sysstat_mem(self):
        ret = {}

        ret['mem_avail'] = True
        try:
            ret['mem'] = psutil.virtual_memory()
        except AttributeError as e:
            ret['mem_avail'] = False

        ret['swap_avail'] = True
        try:
            ret['swap'] = psutil.swap_memory()
        except AttributeError as e:
            ret['swap_avail'] = False
        
        return ret


    def return_status(self):
        ret = {}
        ret['uptime'] = time.time() - psutil.get_boot_time()

        cpus = psutil.cpu_percent(interval=1, percpu=True)
        ret['cpuThreadsLoad'] = []
        total = float()
        for cpu in cpus:
            total += cpu
            ret['cpuThreadsLoad'].append(cpu)
        ret['cpuLoadAvg'] = int(total / psutil.NUM_CPUS)
        ret['cpuThreads'] = len(cpus)

        data = self.get_sysstat_mem()

        if data['mem_avail']:
            ret['ramTotal'] = data['mem'].total
            ret['ramFree'] = data['mem'].free
            ret['ramAvail'] = data['mem'].available
            ret['ramUsed'] = data['mem'].used
            ret['ramPercent'] = data['mem'].percent
        else:
            ret['ramTotal'] = 0
            ret['ramFree'] = 0
            ret['ramAvail'] = 0
            ret['ramUsed'] = 0
            ret['ramPercent'] = 0

        if data['swap_avail']:
            ret['swapTotal'] = data['swap'].total
            ret['swapFree'] = data['swap'].free
            ret['swapUsed'] = data['swap'].used
            ret['swapPercent'] = data['swap'].percent
        else:
            ret['swapTotal'] = 0
            ret['swapFree'] = 0
            ret['swapUsed'] = 0
            ret['swapPercent'] = 0

        return ret

descriptor = {
    'name' : 'sysstat',
    'help' : 'Psutil system information',
    'command' : 'stat',
    'mode' : PluginMode.AUTOLOAD,
    'class' : SysstatPlugin,
    'detailsNames' : { 'uptime' : "System uptime",
                       'cpuLoadAvg' : "Cpu load average percent",
                       'cpuThreads' : "Cpu threads",
                       'cpuThreadsLoad' : "Cpu threads Load percents",
                       'ramTotal' : "Ram total",
                       'ramFree' : "Ram free",
                       'ramAvail' : "Ram available",
                       'ramUsed' : "Ram used",
                       'ramPercent' : "Ram used percent",
                       'swapTotal' : "Swap total",
                       'swapFree' : "Swap free",
                       'swapUsed' : "Swap used",
                       'swapPercent' : "Swap used percent"}
}

