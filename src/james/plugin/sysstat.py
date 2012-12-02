
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
		for partition in partitions:
			usage = psutil.disk_usage(partition.mountpoint)
			print ("%s on %s as %s has %s\% used and %s free" %
					 partition.device, partition.mountpoint, partition.fstype, usage.percent, usage.free)

	def cmd_sysstat_uptime(self, args):
		print int(psutil.BOOT_TIME).round(0)
		print int(time.time()).round(0)

Factory.register_plugin(SysstatPlugin)
