#!/usr/bin/python

from carrot.connection import BrokerConnection
conn = BrokerConnection(hostname="localhost", port=5672,userid="test", password="test",virtual_host="test")

from carrot.messaging import Publisher
publisher = Publisher(connection=conn,exchange="feed", routing_key="alert")
publisher.send({"header": "msg header", "body": "msg body"})
publisher.close()

