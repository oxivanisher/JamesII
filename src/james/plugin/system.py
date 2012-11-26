
import commands

from datetime import timedelta
from james.plugin import *

class SystemPlugin(Plugin):

	name = 'system'

	def __init__(self, core):
		super(SystemPlugin, self).__init__(core, SystemPlugin.name)

		self.create_command('echo', self.cmd_echo, 'echos some text')
		self.create_command('show', self.cmd_show, 'show whatever')
		self.create_command('uptime', self.cmd_uptime, 'show uptime')
		self.create_command('who', self.cmd_who, 'who is currently logged in')
		self.create_command('getip', self.cmd_getip, 'get the ip of the host')

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

	if os.path.isfile('/usr/bin/who'):
		def cmd_who(self, args):
			who_pipe = os.popen('/usr/bin/who','r')
			who = who_pipe.read().strip()
			who_pipe.close()
			return who

	def cmd_getip(self, args):
		return commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | " +
                         "awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'")



Factory.register_plugin(SystemPlugin)
