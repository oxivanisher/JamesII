
class Config (object):
	def __init__(self, filename = 'config.ini'):
		self.filename = filename

		self.values = { 'broker' : { 'host' : 'localhost', 'port' : '5672', 'user' : 'test', 'password' : 'test', 'vhost' : 'test'  }  }


	def load (self):
		pass
