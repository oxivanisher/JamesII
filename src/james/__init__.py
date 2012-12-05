
import json
import pika
import socket
import time

import plugin
import config
import jamesutils

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
		print 'JamesII starting up'

		self.plugins = []
		self.terminated = False
		self.hostname = socket.getfqdn(socket.gethostname())
		self.startup_timestamp = time.time()
		self.utils = jamesutils.JamesUtils(self)
		self.master = False


		try:
			self.brokerconfig = config.BrokerConfig("../config/broker.ini")
		except Exception as e:
			raise ConfigNotLoaded()

		self.config = None
		try:
			self.config = config.Config("../config/config.ini")
			self.master = True
			print("Found master config")
		except Exception as e:
			print("No master config -> client mode")

		# Create global connection
		try:
			self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.brokerconfig.values['broker']['host']))
		except Exception as e:
			raise ConnectionError()

		self.discovery_channel = BroadcastChannel(self, 'discovery')
		self.config_channel = BroadcastChannel(self, 'config')

		self.discovery_channel.add_listener(self.discovery_listener)
		self.config_channel.add_listener(self.config_listener)

		self.discovery_channel.send(['hello', self.hostname])

		if not self.config:
			print("Waiting for config")			
			while not self.config:
				self.connection.process_data_events()

		self.request_channel = BroadcastChannel(self, 'request')
		self.response_channel = BroadcastChannel(self, 'response')

		self.request_channel.add_listener(self.request_listener)
		self.response_channel.add_listener(self.response_listener)


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


	def discovery_listener(self, msg):
		if msg[0] == 'hello':
			print("Discovered new host '%s'" % (msg[1]))
			if self.master:
				self.config_channel.send(self.config.get_values())
#		for p in self.plugins:
#			p.handle_request(msg['uuid'], msg['name'], msg['body'])

	def config_listener(self, msg):
		if not self.config:
			print("Received config");
			self.config = config.Config()
			self.config.set_values(msg)
#		for p in self.plugins:
#			p.handle_response(msg['uuid'], msg['name'], msg['body'])


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
