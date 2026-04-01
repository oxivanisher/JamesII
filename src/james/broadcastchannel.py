import json
import pika
import time
import logging

from james.command import Command


class _JamesEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Command):
            return obj.to_dict()
        return super().default(obj)


def _james_decoder(d):
    if d.get('__type__') == 'Command':
        return Command.from_dict(d)
    return d


class BroadcastChannel:
    def __init__(self, core, name):
        self.core = core
        self.name = name
        self.core.rabbitmq_channels.append(self)
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

        body = json.dumps(msg, cls=_JamesEncoder).encode('utf-8')

        while not msg_sent:
            try:
                self.core.lock_core()
                try:
                    self.channel.basic_publish(exchange=self.name, routing_key='', body=body)
                finally:
                    self.core.unlock_core()
                msg_sent = True
            except pika.exceptions.ConnectionClosed:
                try_count += 1
                if try_count >= 20:
                    logger.warning("Stopping to send msg!")
                    msg_sent = True
                else:
                    logger.info(f"Unable to send msg <{self.name}>. Will retry in 3 sec")
                    time.sleep(3)

    def recv(self, channel, method, properties, body):
        try:
            msg = json.loads(body.decode('utf-8'), object_hook=_james_decoder)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logging.getLogger('broadcastchannel').warning(
                f"Dropping undecodable message on '{self.name}' channel "
                f"(likely a pickle message from an outdated node): {e}"
            )
            return

        for listener in self.listeners:
            listener(msg)

    def add_listener(self, handler):
        self.listeners.append(handler)

# FIXME add class for send and recv handlers
