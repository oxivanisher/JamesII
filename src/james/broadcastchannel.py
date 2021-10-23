
import pickle
import pika
import time
import logging


class BroadcastChannel(object):
    def __init__(self, core, name):
        self.core = core
        self.name = name
        self.listeners = []

        self.channel = self.core.connection.channel()
        self.channel.exchange_declare(exchange=self.name, exchange_type='fanout')
        self.queue_name = self.channel.queue_declare('', exclusive=True).method.queue

        self.channel.queue_bind(exchange=self.name, queue=self.queue_name)

        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.recv, auto_ack=True)

    def send(self, msg):
        logger = logging.getLogger('broadcastchannel')
        msg_sent = False
        try_count = 0

        body = pickle.dumps(msg)

        while not msg_sent:
            try:
                self.channel.basic_publish(exchange=self.name, routing_key='', body=body)
                msg_sent = True
            except pika.exceptions.ConnectionClosed:
                try_count += 1
                if try_count >= 20:
                    logger.warning("Stopping to send message!")
                    msg_sent = True
                else:
                    logger.info("Unable to send message <%s>. Will retry in 3 sec")
                    time.sleep(3)

    def recv(self, channel, method, properties, body):
        msg = pickle.loads(body)

        for listener in self.listeners:
            listener(msg)

    def add_listener(self, handler):
        self.listeners.append(handler)

#FIXME add class for send and recv handlers
