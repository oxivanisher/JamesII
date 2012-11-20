
from datetime import timedelta
from james.plugin import *

class SystemPlugin(Plugin):

	name = 'system'

	def __init__(self, core):
		super(SystemPlugin, self).__init__(core, SystemPlugin.name)

		self.create_command('echo', self.cmd_echo, 'echos some text')
		self.create_command('show', self.cmd_show, 'show whatever')
		self.create_command('uptime', self.cmd_uptime, 'show uptime')

	def terminate(self):
		pass

	def cmd_echo(self, args):
		print 'cmd echo'
		return args[0]

	def cmd_show(self, args):
		print 'cmd show'
		return 'some text'

	def cmd_uptime(self, args):
		with open('/proc/uptime', 'r') as f:
		    uptime_seconds = float(f.readline().split()[0])
    		uptime_string = str(timedelta(seconds = uptime_seconds))
    		return uptime_string




Factory.register_plugin(SystemPlugin)
