
import time

class JamesMessage (object):

	def __init__(self, plugin):
		self.timestamp = time.time()

		self.sender_host = plugin.core.hostname
		self.sender_uuid = plugin.uuid
		self.sender_plugin = plugin.name

		self.reciever_host = None
		self.reciever_uuid = None
		self.reciever_plugin = None

		self.message = None
		self.header = None
		self.level = 0 #0: Debug, 1: Info, 2: Warn, 3: Error


