
import threading
import sys
import yaml

from james.plugin import *

class ConsoleThread(threading.Thread):

	def __init__(self, plugin):
		super(ConsoleThread, self).__init__()
		self.plugin = plugin
		self.terminated = False

	def run(self):
		while (not self.terminated):
			try:
				sys.stdout.write('# ')
				line = sys.stdin.readline()
			except KeyboardInterrupt:
				self.plugin.core.terminate()
			line = line.strip()
			if (line == 'exit'):
				self.plugin.core.terminate()
			elif (line == 'dump_config'):
				print("Dumping config:")
				print(yaml.dump(self.plugin.core.config))

			args = line.split(' ')
			self.plugin.send_command(args)

	def terminate(self):
		self.terminated = True


class CliPlugin(Plugin):

	def __init__(self, core):
		super(CliPlugin, self).__init__(core, CliPlugin.name)

		self.console_thread = ConsoleThread(self)

		sys.stdout.write('Interactive cli interface to james online. server: ')
		sys.stdout.write(self.core.brokerconfig['host'] + ':')
		sys.stdout.write('%s\n' % (self.core.brokerconfig['port']))
		sys.stdout.write('basic commands are help, dump_config and exit.' + '\n')

		self.console_thread.start()

	def terminate(self):
		self.console_thread.terminate()

	def process_command_response(self, args):
		print '\n'.join(args)





descriptor = {
	'name' : 'cli',
	'mode' : PluginMode.MANUAL,
	'class' : CliPlugin
}
