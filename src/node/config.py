import os
from ConfigParser import RawConfigParser

class Config (object):
	def __init__(self, filename = 'config.ini'):
		self.filename = '../config/' + filename
		config = RawConfigParser()

		try:
			if os.path.isfile(self.filename):
				config.read(self.filename)
			elif os.path.isfile('../config/config.ini'):
				config.read('../config/config.ini')
		except:
			print("No cofiguration file found")
			quit()
			
		
		self.values = { 'broker' : { 'host' : config.get('broker','host'),
									 'port' : config.get('broker','port'),
									 'user' : config.get('broker','user'),
									 'password' : config.get('broker','password'),
									 'vhost' : config.get('broker','vhost') }}


	def load (self):
		pass
