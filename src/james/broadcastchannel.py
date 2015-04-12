
# import pickle
import json
import pika
import time
import logging

class BroadcastChannel(object):
    def __init__(self, core, name):
        self.core = core
        self.name = name
        self.listeners = []
        self.log = jamesutils.getLogger('broadcastchannel')

        self.channel = self.core.connection.channel()
        self.channel.exchange_declare(exchange=self.name, type='fanout')
        self.queue_name = self.channel.queue_declare(exclusive=True).method.queue

        self.channel.queue_bind(exchange=self.name, queue=self.queue_name)

        self.channel.basic_consume(self.recv, queue=self.queue_name, no_ack=True)

    def send(self, msg):
        logger = logging.getLogger('broadcastchannel')
        msgSent = False
        tryCount = 0
        body = json.dumps(msg)
        while not msgSent:
            try:
                self.channel.basic_publish(exchange=self.name, routing_key='', body=body)
                msgSent = True
            except pika.exceptions.ConnectionClosed:
                tryCount += 1
                if tryCount >= 20:
                    logger.warning("Stopping to send message!")
                    msgSent = True
                else:
                    logger.info("Unable to send message <%s>. Will retry in 3 sec")
                    time.sleep(3)

    def recv(self, channel, method, properties, body):
        msg = json.loads(body)
        for listener in self.listeners:
            listener(msg)

    def add_listener(self, handler):
        self.listeners.append(handler)

#FIXME add class for send and recv handlers
