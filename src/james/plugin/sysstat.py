
import sys
import time
import psutil

from james.plugin import *

class SysstatPlugin(Plugin):

	name = 'sysstat'

	def __init__(self, core):
		super(SysstatPlugin, self).__init__(core, SysstatPlugin.name)

		self.create_command('sysstat_mount', self.cmd_sysstat_mount, 'show mounted partitions')
		self.create_command('sysstat_uptime', self.cmd_sysstat_uptime, 'show system uptime')

	def terminate(self):
		pass

	def cmd_sysstat_mount(self, args):
		partitions = psutil.disk_partitions()
		return_str = []
		for partition in partitions:
			usage = psutil.disk_usage(partition.mountpoint)
			return_str.append("%s on %s as %s has %s%% used and %s free." %
					(partition.device, partition.mountpoint, partition.fstype, usage.percent, usage.free))
		return return_str

	def cmd_sysstat_uptime(self, args):
		sys_uptime = int(round(time.time(), 0)) - int(round(psutil.BOOT_TIME, 0))
		james_uptime = int(round(time.time(), 0)) - int(round(self.core.startup_timestamp, 0))
		return 'The System is running since %s seconds, JamesII since %s seconds.' % (sys_uptime, james_uptime)

Factory.register_plugin(SysstatPlugin)
