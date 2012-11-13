#!/usr/bin/env python

import subprocess
import os
import sys
import xmpp
import time
from carrot.messaging import Consumer

import node

class Xmpp(node.Base):
	def __init__(self):
		super(Xmpp, self).__init__('espeak')
		self.consumer = Consumer(connection=self.conn, queue="espeak",exchange="feed", routing_key="alert")
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
		print(self.config.values['xmpp_alert']['user'])
		text = ' '.join(header + "\n" + body)
		

#		if len(sys.argv) < 2:
#		    print "Syntax: xsend JID text"
#		    sys.exit(0)
#		
#		tojid=sys.argv[1]
#		text=' '.join(sys.argv[2:])
#		
#		jidparams={}
#		if os.access(os.environ['HOME']+'/.xsend',os.R_OK):
#		    for ln in open(os.environ['HOME']+'/.xsend').readlines():
#		        if not ln[0] in ('#',';'):
#		            key,val=ln.strip().split('=',1)
#		            jidparams[key.lower()]=val
#		for mandatory in ['jid','password']:
#		    if mandatory not in jidparams.keys():
#		        open(os.environ['HOME']+'/.xsend','w').write('#Uncomment fields before use and type in correct credentials.\n#JID=romeo@montague.net/resource (/resource is optional)\n#PASSWORD=juliet\n')
#		        print 'Please point ~/.xsend config file to valid JID for sending messages.'
#		        sys.exit(0)
#		
#		jid=xmpp.protocol.JID(jidparams['jid'])
#		cl=xmpp.Client(jid.getDomain(),debug=[])
		jid=xmpp.protocol.JID(self.config.values['xmpp_alert']['user'])
		cl=xmpp.Client(jid.getDomain(),debug=[])
#		
		con=cl.connect()
		if not con:
		    print 'could not connect!'
		    sys.exit()
		print 'connected with',con
		auth=cl.auth(jid.getNode(),jidparams['password'],resource=jid.getResource())
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



node = Xmpp()
node.run()

#say_pipe = os.popen('/usr/bin/espeak "' + args + '"', 'r')
#sayp = say_pipe.read().strip()
#say_pipe.close()
