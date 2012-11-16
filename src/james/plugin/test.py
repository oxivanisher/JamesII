
from james.plugin import *

class TestPlugin(Plugin):

	name = 'test'

	def __init__(self, core):
		super(TestPlugin, self).__init__(core, TestPlugin.name)

		self.create_command('echo', self.cmd_echo, 'echos some text')
		self.create_command('show', self.cmd_show, 'show whatever')

	def cmd_echo(self, args):
		self.core.output(args[0])

	def cmd_show(self, args):
		self.core.output("list some")




Factory.register_plugin(TestPlugin)
