
import time
import uuid

class JamesMessage (object):

	def __init__(self, core, name):
		self.timestamp = time.time()

		self.sender_host = core.hostname
		self.sender_uuid = str(uuid.uuid1())
		self.sender_name = name

		self.reciever_host = None
		self.reciever_uuid = None
		self.reciever_name = None

		self.message = None
		self.header = None
		self.level = 0 #0: Debug, 1: Info, 2: Warn, 3: Error

		self.payload = None
