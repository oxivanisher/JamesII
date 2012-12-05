
import threading
import sys

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

			args = line.split(' ')
			self.plugin.send_command(args)

	def terminate(self):
		self.terminated = True


class CliPlugin(Plugin):

	name = 'cli'

	def __init__(self, core):
		super(CliPlugin, self).__init__(core, CliPlugin.name)

		self.console_thread = ConsoleThread(self)

		sys.stdout.write('interactive cli interface to james online. server: ')
		sys.stdout.write(self.core.brokerconfig.values['broker']['host'] + ':')
		sys.stdout.write(self.core.brokerconfig.values['broker']['port'] + '\n')
		sys.stdout.write('basic commands are help and exit.' + '\n')

		self.console_thread.start()

	def terminate(self):
		self.console_thread.terminate()

	def process_command_response(self, args):
		print '\n'.join(args)


Factory.register_plugin(CliPlugin)
