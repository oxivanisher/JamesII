import os
import io
import json
#from jsonschema import validate
from ConfigParser import RawConfigParser

class JamesConfig (object):
	def __init__(self, filename):
		self.filename = filename
		self.values = {}
		self.load()

	def load(self):
		self.values = json.loads(open(self.filename).read())

	def save(self):
		#FIXME: untested!
		pass
		with io.open(self.filename, 'w', encoding='utf-8') as outfile:
			json.dumps(self.values, outfile)
		pass

	def get_values(self):
		return self.values

	def set_values(self, values):
		self.values = values


class BrokerConfig (object):
	def __init__(self, filename):
		config = RawConfigParser()

		config.read(filename)
		
		self.values = { 'broker' : { 'host' : config.get('broker','host'),
									 'port' : config.get('broker','port'),
									 'user' : config.get('broker','user'),
									 'password' : config.get('broker','password'),
									 'vhost' : config.get('broker','vhost') }
						}


	def get_values(self):
		return self.values

class Config (object):
	def __init__(self, filename = None):
		self.values = {}

		if not filename:
			return

		config = RawConfigParser()
		config.read(filename)
		
		self.values = { 'xmpp_alert' : { 'jid' : config.get('xmpp_alert','jid'),
									 'password' : config.get('xmpp_alert','password'),
									 'destination' : config.get('xmpp_alert','destination')	},
 						'mpd' : { 'host' : config.get('mpd','host'),
									 'password' : config.get('mpd','password'),
									 'radio_url' : config.get('mpd','radio_url'),
									 'sleep_url' : config.get('mpd','sleep_url'),
									 'wakeup_url' : config.get('mpd','wakeup_url'),
									 'port' : config.get('mpd','port') },
						'core' : { 'timezone' : config.get('core','timezone') }
						}


	def get_values(self):
		return self.values

	def set_values(self, values):
		self.values = values
