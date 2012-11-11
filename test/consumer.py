#!/usr/bin/python

from carrot.connection import BrokerConnection
from carrot.messaging import Consumer
conn = BrokerConnection(hostname="localhost", port=5672,userid="test", password="test",virtual_host="test")
consumer = Consumer(connection=conn, queue="feed",exchange="feed", routing_key="importer")

def import_feed_callback(message_data, message):
	feed_url = message_data["import_feed"]
	print("Got feed import message for: %s" % feed_url)
	# something importing this feed url
	# import_feed(feed_url)
	message.ack()
consumer.register_callback(import_feed_callback)
consumer.wait() # Go into the consumer loop.



