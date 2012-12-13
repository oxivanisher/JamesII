

class Command(object):

	def __init__(self, name, help, handler):
		self.name = name
		self.help = help
		self.handler = handler
		self.subcommands = {}

	def add_subcommand(self, subcommand):
		try:
			return self.subcommands[subcommand.name]
		except KeyError:
			self.subcommands[subcommand.name] = subcommand
			return subcommand

	# creates a new subcommand and returns reference to it
	def create_subcommand(self, name, help, handler):
		cmd = Command(name, help, handler)
		return self.add_subcommand(cmd)

	def process_args(self, args):
		print('execute cmd ', self.name)

		if self.handler:
			self.handler()

		if len(args) < 1:
			return

		try:
			self.subcommands[args[0]].process_args(args[1:])
		except KeyError:
			pass

	def dump(self, indent = ''):
		print indent + self.name
		for subcommand in self.subcommands.keys():
			self.subcommands[subcommand].dump(indent + '\t')


def list_cmd_handler():
	print "cmd_handler"

root_cmd = Command('root', '', None)

xmpp_cmd = root_cmd.create_subcommand('xmpp', 'xmpp plugin', None)

xmpp_cmd.create_subcommand('list', 'list files', list_cmd_handler)
xmpp_cmd.create_subcommand('list2', 'list files', list_cmd_handler)

root_cmd.dump()

root_cmd.process_args(['xmpp', 'list1'])