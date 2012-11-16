
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
		self.name = name
		self.core = core
		self.cmds = {}

		self.create_command('help', self.cmd_help, "Show information about plugins commands", True)

	def add_command(self, command):
		self.cmds[command.name] = command

	def create_command(self, name, handler, help="", hide=False):
		self.add_command(Command(name, handler, help, hide))

	def execute_command(self, args):
		if len(args) < 1:
			return

		try:
			self.cmds[args[0]].handler(args[1:])
		except KeyError:
			raise CommandNotFound()


	def cmd_help(self, args):
		for cmd in self.cmds.values():
			if not cmd.hide:
				self.core.output("%-10s - %s" % (cmd.name, cmd.help))


class Factory(object):

	plugins = {}

	@classmethod
	def register_plugin(cls, plugin):
		cls.plugins[plugin.name] = plugin



# Load plugins
import test
