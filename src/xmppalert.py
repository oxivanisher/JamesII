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
		self.consumer = Consumer(connection=self.conn, queue="xmpp", exchange_type="topic", exchange="james", routing_key="*")
		self.consumer.register_callback(self.import_feed_callback)

	def import_feed_callback(self, message_data, message):
		message.ack()
		header = message_data["header"]
		body = message_data["body"]
		
		print("Header: %s; Body: %s" % (header, body))
		self.xmpp_send(header, body)
		
	def xmpp_send(self, header, body):
		text = header + "\n" + body
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
		
		id=cl.send(xmpp.protocol.Message(tojid,text,'chat'))
		print 'sent message with id',id
		
		cl.disconnect()
		
	def run(self):
		self.consumer.wait() # Go into the consumer loop.


node = XmppAlert()
node.run()
