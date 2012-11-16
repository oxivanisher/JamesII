#!/usr/bin/env python

import sys
from carrot.messaging import Publisher


import node

class Cli(node.Base):
	def __init__(self):
		super(Cli, self).__init__('cli')

		self.publisher = Publisher(connection=self.conn, exchange_type="topic", exchange="james", routing_key="alert")

	def __del__(self):
		super(Cli, self).__del__()

		self.publisher.close() 
		
	

	def execute(self, args):
		if len(args) == 0:
			print("No command specified")
			return

		cmd = args[0]

		cmds = { 'alert' : self.cmd_alert }

		try:
			cmds[cmd](args[1:])
		except KeyError:
			print("Unknown command")

		pass


	def cmd_alert(self, args):
		self.publisher.send({"header": args[0], "body": args[1]})
		print "alert:", args


node = Cli()
node.execute(sys.argv[1:])
