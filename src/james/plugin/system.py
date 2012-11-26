
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
		self.create_command('get_node_ip', self.cmd_get_ip, 'get the ip of the node')
		self.create_command('get_node_name', self.cmd_get_node_name, 'get the name of the node')
		self.create_command('get_node_info', self.cmd_get_node_info, 'get the name and ip of the node')


	def terminate(self):
		pass

	def cmd_echo(self, args):
		print 'cmd echo'
		if args.has_key(0):
			args[0] = 'you entered no text to echo...'
		return args[0]

	def cmd_show(self, args):
		print 'cmd show'
		return 'some text'

	def cmd_uptime(self, args):
		print 'cmd uptime'
		with open('/proc/uptime', 'r') as f:
		    uptime_seconds = float(f.readline().split()[0])
    		uptime_string = str(timedelta(seconds = uptime_seconds))
    		return uptime_string

	if os.path.isfile('/usr/bin/who'):
		def cmd_who(self, args):
			print 'cmd who'
			who_pipe = os.popen('/usr/bin/who','r')
			who = who_pipe.read().strip()
			who_pipe.close()
			return who

	def cmd_get_ip(self, args):
		print 'cmd get_ip'
		return self.get_ip()

	def cmd_get_node_name(self, args):
		print 'cmd get_node_name'
		return self.core.hostname

	def cmd_get_node_info(self, args):
		print 'cmd get_node_info'
		return "%-15s - %s" % (self.get_ip(), self.core.hostname)


	# Helper Methods
	def get_ip(self):
		return commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | " +
                         "awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'")


Factory.register_plugin(SystemPlugin)
