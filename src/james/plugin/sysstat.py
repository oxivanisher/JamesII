import time
import psutil

from james.plugin import *


class SysstatPlugin(Plugin):

    def __init__(self, core, descriptor):
        super().__init__(core, descriptor)

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
            return_str.append(f"{partition.device} on {partition.mountpoint} as {partition.fstype} has {usage.percent}% used and {usage.free} free.")
        return return_str

    def sysstat_uptime(self, args):
        return ([f'The System started {self.utils.get_nice_age(int(round(psutil.BOOT_TIME, 0)))}, JamesII {self.utils.get_nice_age(int(round(self.core.startup_timestamp, 0)))}.'
])

    def sysstat_net(self, args):
        interfaces = psutil.network_io_counters(pernic=True)
        return_str = []
        for interface in interfaces:
            if interface != "lo":
                net_interface = interfaces[interface]
                return_str.append(f"{interface:<5} Sent: {self.utils.bytes2human(net_interface.bytes_sent):<8} Recv: {self.utils.bytes2human(net_interface.bytes_recv):<8}")
        return return_str

    def sysstat_who(self, args):
        users = psutil.get_users()
        return_str = []
        for user in users:
            return_str.append(f"{user.name:<15} {user.terminal or '-':<15} {self.utils.get_short_age(user.started)} ({user.host})")
        return return_str

    def sysstat_cpu(self, args):
        return_str = []
        total = float()
        ret_str = ""
        cpus = psutil.cpu_percent(interval=1, percpu=True)
        for cpu in cpus:
            total += cpu
            ret_str += f"{int(cpu):4}%"
        return_str.append(f"load avg {int(total / psutil.NUM_CPUS):3}%; threads {ret_str}")
        return return_str

    def sysstat_mem(self, args):
        data = self.get_sysstat_mem()

        return_str = []

        if data['mem_avail']:
            return_str.append(f"memory used {self.utils.bytes2human(data['mem'].used)}/{self.utils.bytes2human(data['mem'].total)} {data['mem'].percent}%; avail {self.utils.bytes2human(data['mem'].available)}; free {self.utils.bytes2human(data['mem'].free)}")

        if data['swap_avail']:
            return_str.append(f"swap used {self.utils.bytes2human(data['swap'].used)}/{self.utils.bytes2human(data['swap'].total)} {data['swap'].percent}%; free {self.utils.bytes2human(data['swap'].free)}")

        return return_str

    def get_sysstat_mem(self):
        ret = {'mem_avail': True}

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

    def return_status(self, verbose=False):
        ret = {}
        try:
            ret['uptime'] = time.time() - psutil.boot_time()
        except AttributeError:
            ret['uptime'] = time.time() - psutil.BOOT_TIME

        cpus = psutil.cpu_percent(interval=1, percpu=True)
        ret['cpuThreadsLoad'] = []
        total = float()
        for cpu in cpus:
            total += cpu
            ret['cpuThreadsLoad'].append(cpu)

        try:
            ret['cpuLoadAvg'] = int(total / psutil.cpu_count())
        except AttributeError:
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
    'name': 'sysstat',
    'help_text': 'Psutil system information',
    'command': 'stat',
    'mode': PluginMode.AUTOLOAD,
    'class': SysstatPlugin,
    'detailsNames': {'uptime': "System uptime",
                     'cpuLoadAvg': "Cpu load average percent",
                     'cpuThreads': "Cpu threads",
                     'cpuThreadsLoad': "Cpu threads Load percents",
                     'ramTotal': "Ram total",
                     'ramFree': "Ram free",
                     'ramAvail': "Ram available",
                     'ramUsed': "Ram used",
                     'ramPercent': "Ram used percent",
                     'swapTotal': "Swap total",
                     'swapFree': "Swap free",
                     'swapUsed': "Swap used",
                     'swapPercent': "Swap used percent"}
}
