
import plugin

class PluginNotFound(Exception):
	pass


class TextChannel(object):
	def __init__(self, core):
		self.core = core
		self.listeners = []

	def write(self, text):
		for listener in self.listeners:
			listener(text)

	def add_listener(self, handler):
		self.listeners.append(handler)



class Core(object):
	def __init__(self):

		self.plugins = []

		self.input_channel = TextChannel(self)
		self.output_channel = TextChannel(self)

		self.input_channel.add_listener(self.input_channel_handler)
		self.output_channel.add_listener(self.output_channel_handler)

		self.load_plugin('test')

	def load_plugin(self, name):
		try:
			cls = plugin.Factory.plugins[name]
		except KeyError:
			raise PluginNotFound()

		# Intantiate plugin instance
		p = cls(self)

		self.plugins.append(p)

	def execute_command(self, text):
		""" Executes a command locally. """
		args = text.split(" ")

		if len(args) < 1:
			return

		for p in self.plugins:
			if p.name == args[0]:
				p.execute_command(args[1:])

	def input_channel_handler(self, text):
		self.execute_command(text)

	def output_channel_handler(self, text):
		print(text)

	def output(self, text):
		""" Sends text output to the queue. """
		self.output_channel.write(text)

	def send_command(self, args):
		""" Sends a command to the queue. """
		pass


	def run(self):
		pass
