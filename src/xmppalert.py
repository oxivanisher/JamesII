#!/usr/bin/env python

import subprocess
import os
import sys
import xmpp
import time
from carrot.messaging import Consumer

import node

class XmppAlert(node.Base):
	def __init__(self):
		super(XmppAlert, self).__init__('xmppalert')
		self.consumer = Consumer(connection=self.conn, queue="alert",exchange="feed", routing_key="alert")
		self.consumer.register_callback(self.import_feed_callback)

	def import_feed_callback(self, message_data, message):
		message.ack()
		header = message_data["header"]
		body = message_data["body"]
		
		print("Header: %s; Body: %s" % (header, body))
		self.xmpp_send(header, body)
		# something importing this feed url
		# import_feed(feed_url)

		
	def xmpp_send(self, header, body):
		text = ' '.join(header + "\n" + body)
		tojid = self.config.values['xmpp_alert']['destination']
		
		jid=xmpp.protocol.JID(self.config.values['xmpp_alert']['jid'])
		cl=xmpp.Client(jid.getDomain(),debug=[])

		con=cl.connect()
		if not con:
		    print 'could not connect!'
		    sys.exit()
		print 'connected with',con
		auth=cl.auth(jid.getNode(),self.config.values['xmpp_alert']['password'],resource=jid.getResource())
		if not auth:
		    print 'could not authenticate!'
		    sys.exit()
		print 'authenticated using',auth
		
		#cl.SendInitPresence(requestRoster=0)   # you may need to uncomment this for old server
		id=cl.send(xmpp.protocol.Message(tojid,text))
		print 'sent message with id',id
		
		time.sleep(1)   # some older servers will not send the message if you disconnect immediately after sending
		
		#cl.disconnect()
		
	def run(self):
		self.consumer.wait() # Go into the consumer loop.



node = XmppAlert()
node.run()

#say_pipe = os.popen('/usr/bin/espeak "' + args + '"', 'r')
#sayp = say_pipe.read().strip()
#say_pipe.close()
