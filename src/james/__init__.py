
import config
import json
import pika
import plugin

class PluginNotFound(Exception):
	pass
class ConfigNotLoaded(Exception):
	pass
class ConnectionError(Exception):
	pass

class BroadcastChannel(object):
	def __init__(self, core, name):
		self.core = core
		self.name = name
		self.listeners = []

		self.channel = self.core.connection.channel()
		self.channel.exchange_declare(exchange=self.name, type='fanout')
		self.queue_name = self.channel.queue_declare(exclusive=True).method.queue

		self.channel.queue_bind(exchange=self.name, queue=self.queue_name)

		self.channel.basic_consume(self.recv, queue=self.queue_name, no_ack=True)

	def send(self, msg):
		body = json.dumps(msg)
		self.channel.basic_publish(exchange=self.name, routing_key='', body=body)

	def recv(self, channel, method, properties, body):
		msg = json.loads(body)
		for listener in self.listeners:
			listener(msg)

	def add_listener(self, handler):
		self.listeners.append(handler)



class Core(object):
	def __init__(self):

		self.plugins = []

		try:
			self.config = config.Config(["../config/config.ini"])
		except Exception as e:
			raise ConfigNotLoaded()

		# Create global connection
		try:
			self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.config.values['broker']['host']))
		except Exception as e:
			raise ConnectionError()

		self.request_channel = BroadcastChannel(self, 'request')
		self.response_channel = BroadcastChannel(self, 'response')

		self.request_channel.add_listener(self.request_listener)
		self.response_channel.add_listener(self.response_listener)

		self.terminated = False

	def load_plugin(self, name):
		try:
			cls = plugin.Factory.plugins[name]
		except KeyError:
			raise PluginNotFound()

		# Intantiate plugin instance
		p = cls(self)

		self.plugins.append(p)

	def send_request(self, uuid, name, body):
		"""Sends a request."""
		self.request_channel.send({'uuid': uuid, 'name': name, 'body': body})

	def send_response(self, uuid, name, body):
		self.response_channel.send({'uuid': uuid, 'name': name, 'body': body})

	def request_listener(self, msg):
		for p in self.plugins:
			p.handle_request(msg['uuid'], msg['name'], msg['body'])

	def response_listener(self, msg):
		for p in self.plugins:
			p.handle_response(msg['uuid'], msg['name'], msg['body'])


	def run(self):
		while not self.terminated:
			try:
				self.connection.process_data_events()
			except KeyboardInterrupt:
				self.terminate()
		
	def terminate(self):
		for p in self.plugins:
			p.terminate()
		self.terminated = True
