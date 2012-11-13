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
			sys.exit(1)
			
		
		self.values = { 'broker' : { 'host' : config.get('broker','host'),
									 'port' : config.get('broker','port'),
									 'user' : config.get('broker','user'),
									 'password' : config.get('broker','password'),
									 'vhost' : config.get('broker','vhost') },
						'xmpp_alert' : { 'jid' : config.get('xmpp_alert','jid'),
									 'password' : config.get('xmpp_alert','password'),
									 'destination' : config.get('xmpp_alert','destination')	}
						}


	def load (self):
		pass
