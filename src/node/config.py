import os
from ConfigParser import RawConfigParser

class ConfigException (Exception):
	pass

class Config (object):
	def __init__(self, filenames = []):
		config = RawConfigParser()

		config.read(filenames)
		
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
