
import os
import json
import pika
import socket
import time
import sys
import uuid
import copy

import plugin
import config
import jamesutils
import jamesmessage


# Pika SUPER HACK
try:
    pika.adapters.blocking_connection.log
except AttributeError:
    class PikaLogDummy(object):
        def debug(*args):
            pass
    pika.adapters.blocking_connection.log = PikaLogDummy()


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

class ProximityStatus(object):
    def __init__(self, core):
        self.status = {}
        self.status['home'] = False
        self.core = core

    def set_status_here(self, value, plugin):
        if self.status[self.core.location] != value:
            self.core.proximity_event(value, plugin)
    
    def update_all_status(self, newstatus, plugin):
        if self.status != newstatus:
            fire_event = True
        else:
            fire_event = False

        self.status = newstatus

        if fire_event:
            self.core.proximity_event(newstatus[self.core.location], plugin)

    def get_all_status(self):
        return self.status

    def get_all_status_copy(self):
        return copy.deepcopy(self.status)

    def get_status_here(self):
        return self.status[self.core.location]

class Core(object):
    def __init__(self, passive = False):
        output = 'JamesII starting up'

        self.plugins = []
        self.terminated = False
        self.hostname = socket.gethostname()
        self.startup_timestamp = time.time()
        self.utils = jamesutils.JamesUtils(self)
        self.master = False
        self.uuid = str(uuid.uuid1())
        self.proximity_status = ProximityStatus(self)
        self.location = 'home'

        # Load broker configuration
        try:
            self.brokerconfig = config.YamlConfig("../config/broker.yaml").get_values()
        except Exception as e:
            raise ConfigNotLoaded()

        # Load master configuration
        self.config = None

        try:
            self.config = config.YamlConfig("../config/config.yaml").get_values()
            self.master = True
            mode_output = "master"
        except Exception as e:
            mode_output = "client"

        # check for passive mode
        if passive:
            self.master = False
            self.config = None
            mode_output = "passive"

        # Show welcome header
        print ("%s (%s mode)" % (output, mode_output))

        # Create global connection
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.brokerconfig['host']))
        except Exception as e:
            raise ConnectionError()

        # Create discovery & configuration channels
        self.discovery_channel = BroadcastChannel(self, 'discovery')
        self.discovery_channel.add_listener(self.discovery_listener)
        self.config_channel = BroadcastChannel(self, 'config')
        self.config_channel.add_listener(self.config_listener)

        # Send hello
        self.discovery_channel.send(['hello', self.hostname, self.uuid])

        # Wait for configuration if not master
        if not self.master:
            print("Waiting for config")
            while not self.config:
                self.connection.process_data_events()
        # set some stuff that would be triggered by getting config.
        # this is probably not nicely done.
        else:
            try:
                self.location = self.config['locations'][self.hostname]
            except Exception as e:
                pass

        # Show if we are in debug mode
        if self.config['core']['debug']:
            print("Debug mode activated")

        # Create request & response channels
        self.request_channel = BroadcastChannel(self, 'request')
        self.request_channel.add_listener(self.request_listener)
        self.response_channel = BroadcastChannel(self, 'response')
        self.response_channel.add_listener(self.response_listener)

        # Create messaging channels
        self.message_channel = BroadcastChannel(self, 'message')
        self.message_channel.add_listener(self.message_listener)

        # proximity stuff
        self.proximity_channel = BroadcastChannel(self, 'proximity')
        self.proximity_channel.add_listener(self.proximity_listener)

        # Load plugins
        path = os.path.join(os.path.dirname(__file__), 'plugin')
        plugin.Factory.find_plugins(path)

    # plugin methods
    def load_plugin(self, name):
        try:
            print("Loading plugin '%s'" % (name))
            c = plugin.Factory.get_plugin_class(name)
            self.plugins.append(c(self))
        except plugin.PluginNotAvailable, e:
            print e

    def autoload_plugins(self):

        output = "Ignoring manual plugins:"
        for c in plugin.Factory.enum_plugin_classes_with_mode(plugin.PluginMode.MANUAL):
            output += (" %s" % (c.name))
        if self.config['core']['debug']:
            print(output)

        output = "Autoloading plugins:"
        for c in plugin.Factory.enum_plugin_classes_with_mode(plugin.PluginMode.AUTOLOAD):
            output += (" %s" % (c.name))
            self.plugins.append(c(self))
        if self.config['core']['debug']:
            print(output)

        output = "Loading managed plugins:"
        for c in plugin.Factory.enum_plugin_classes_with_mode(plugin.PluginMode.MANAGED):
            load_plugin = False

            try:
                for mp in self.config[c.name]['nodes']:
                    if mp == self.hostname:
                        load_plugin = True
            except KeyError:
                pass

            if load_plugin:
                output += (" +%s" % (c.name))
                self.plugins.append(c(self))
            else:
                output += (" -%s" % (c.name))

        if self.config['core']['debug']:
            print(output)

    # command channel methods
    def send_request(self, uuid, name, body, host, plugin):
        """Sends a request."""
        self.request_channel.send({'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})

    def send_response(self, uuid, name, body, host, plugin):
        self.response_channel.send({'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})

    def request_listener(self, msg):
        for p in self.plugins:
            p.process_command_request_event(msg)
            p.handle_request(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    def response_listener(self, msg):
        for p in self.plugins:
            p.process_command_response_event(msg)
            p.handle_response(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    # configuration & config channel methods
    def discovery_listener(self, msg):
        if msg[0] == 'hello':
            show_message = True
            try:
                if not self.config['core']['debug']:
                    show_message = False
            except TypeError as e:
                pass

            if show_message and msg[2] != self.uuid:
                print("Discovered new host or instance '%s' (%s)" % (msg[1], msg[2]))

            # Broadcast configuration if master
            if self.master:
                self.config_channel.send(self.config)

        elif msg[0] == 'ping':
            self.discovery_channel.send(['pong', self.hostname, self.uuid])

        for p in self.plugins:
            p.process_discovery_event(msg)

    def config_listener(self, msg):
        if not self.config:
            show_message = True
            try:
                if not self.config['core']['debug']:
                    show_message = False
            except TypeError as e:
                pass

            if show_message:
                print("Received config")

            self.config = msg

            try:
                self.location = self.config['locations'][self.hostname]
            except Exception as e:
                self.location = 'home'
        else:
            if self.config != msg:
                print("The configuration file has changed. Exiting!")
                self.terminate()

    # message channel methods
    def send_message(self, msg):
        self.message_channel.send(msg)

    def new_message(self, name = "uninitialized_message"):
        return jamesmessage.JamesMessage(self, name)

    def message_listener(self, msg):
        message = jamesmessage.JamesMessage(self, "recieved message")
        message.set(msg)
        
        for p in self.plugins:
            p.process_message(message)

    # proximity channel methods
    def proximity_listener(self, msg):
        if self.proximity_status.get_status_here() != msg['status'][self.location]:
            for p in self.plugins:
                p.process_proximity_event(msg)
        self.proximity_status.update_all_status(msg['status'], msg['plugin'])

    def proximity_event(self, changedstatus, pluginname):
        newstatus = {}
        oldstatus = self.proximity_status.get_all_status_copy()

        if oldstatus[self.location] != changedstatus:
            newstatus[self.location] = changedstatus

            message = jamesmessage.JamesMessage(self, "core")
            message.body = ("From %s" % (pluginname))
            message.level = 0
            if changedstatus:
                message.header = "You came back."
            else:
                message.header = "You left."
            message.send()

            self.proximity_channel.send({'status' : newstatus,
                                         'host' : self.hostname,
                                         'plugin' : pluginname,
                                         'location' : self.location })

    # base methods
    def run(self):
        for p in self.plugins:
            p.start()
        while not self.terminated:
            try:
                self.connection.process_data_events()
                #print("process events")
            except KeyboardInterrupt:
                self.terminate()
        
    def terminate(self):
        self.discovery_channel.send(['byebye', self.hostname, self.uuid])
        for p in self.plugins:
            p.terminate()
        print("I shall die now.")
        self.terminated = True

    def add_timeout(self, seconds, handler):
        self.connection.add_timeout(seconds, handler)
