
import uuid
import os
import imp

class CommandNotFound(Exception):
	pass

class Command(object):

	def __init__(self, name, handler, help="", hide=False):
		self.name = name
		self.handler = handler
		self.help = help
		self.hide = hide



class Plugin(object):

	def __init__(self, core, name):
		self.uuid = str(uuid.uuid1())
		self.name = name
		self.core = core
		self.cmds = {}
		self.mode = 0	#0: autoload, 1: managed, 2: exclusive

		self.create_command('help', self.cmd_help, "Show information about plugins commands", True)
		self.create_command('avail', self.cmd_avail, "Show available plugins", True)

	def terminate(self):
		pass

	def add_command(self, command):
		self.cmds[command.name] = command

	def create_command(self, name, handler, help="", hide=False):
		self.add_command(Command(name, handler, help, hide))

	def process_command(self, args):
		args = [s.encode('utf-8').strip() for s in args]
		args = filter(lambda s: s != '', args)
		if len(args) < 1:
			return None

		if args[0][0] == '@':
			if args[0][1:] != self.name:
				return None
			args = args[1:]

		if len(args) < 1:
			return None

		try:
			return self.cmds[args[0]].handler(args[1:])
		except KeyError:
			return None

	def process_command_response(self, args):
		pass

	def send_command(self, args):
		""" Sends a command to the queue. """
		self.send_request(self.uuid, 'cmd', args)

	def send_request(self, uuid, name, body):
		self.core.send_request(uuid, name, body)

	def send_response(self, uuid, name, body):
		self.core.send_response(uuid, name, body)

	def handle_request(self, uuid, name, body):
		if name == 'cmd':
			res = self.process_command(body)
			if res:
				self.send_response(uuid, name, res)

	def handle_response(self, uuid, name, body):
		if uuid == self.uuid:
			if name == 'cmd':
				args = body
				if not isinstance(args, list):
					args = [args]
				self.process_command_response(args)




	def cmd_help(self, args):
		res = []
		for cmd in self.cmds.values():
			if not cmd.hide:
				res.append("%-15s - %s" % (cmd.name, cmd.help))
		return res

	def cmd_avail(self, args):
		return os.uname()[1] + ' ' + self.name


class Factory(object):

	plugins = {}

	@classmethod
	def register_plugin(cls, plugin):
		cls.plugins[plugin.name] = plugin

	@classmethod
	def find_plugins(cls, path):
		files = os.listdir(path)
		for f in files:
			(name, ext) = os.path.splitext(os.path.basename(f))
			if ext != '.py' or name == '__init__':
				continue
			print("Loading plugin '%s'" % (name))
			f = os.path.join(path, f)
			py_mod = imp.find_module(name, [path])
			try:
				imp.load_module(name, *py_mod)
			except ImportError, e:
				print("Failed to load plugin '%s' (%s)" % (name, e))
