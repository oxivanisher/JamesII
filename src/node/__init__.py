import config

import sys
from carrot.connection import BrokerConnection
from carrot.messaging import Consumer

class Base(object):
	def __init__(self, name):
		self.name = name
		print("Node %s starting" % self.name)
		
		try:
			self.config = config.Config([self.name + ".ini", "../config/config.ini"])
		except Exception as e:
			print("ERROR on loading config: " + e)
			sys.exit(1)


		self.conn = BrokerConnection(
						hostname=self.config.values['broker']['host'],
						port=self.config.values['broker']['port'],
						userid=self.config.values['broker']['user'],
						password=self.config.values['broker']['password'],
						virtual_host=self.config.values['broker']['vhost'])
	
	def __del__(self):
		pass

	def run(self):
		pass

	def quit(self, msg = "Exiting node"):
		print(msg)
		sys.exit(0)
