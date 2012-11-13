#!/usr/bin/env python

import subprocess
import sys
from carrot.messaging import Consumer

import node

class EspeakAlert(node.Base):
	def __init__(self):
		super(EspeakAlert, self).__init__('espeak')
		self.consumer = Consumer(connection=self.conn, queue="alert", exchange="feed", routing_key="alert")
		self.consumer.register_callback(self.import_feed_callback)

	def import_feed_callback(self, message_data, message):
		message.ack()
		header = message_data["header"]
		body = message_data["body"]
		
		print("Header: %s; Body: %s" % (header, body))
		self.speak(header)
		# something importing this feed url
		# import_feed(feed_url)

		
	def speak(self, msg):
		subprocess.call(['/usr/bin/espeak', msg])
		
	def run(self):
		self.consumer.wait() # Go into the consumer loop.



node = EspeakAlert()
node.run()

#say_pipe = os.popen('/usr/bin/espeak "' + args + '"', 'r')
#sayp = say_pipe.read().strip()
#say_pipe.close()
