
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
import command
import broadcastchannel
import proximitystatus
import jamesutils
import jamesmessage

#from james_classes import BroadcastChannel, ProximityStatus, Command


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
        self.proximity_status = proximitystatus.ProximityStatus(self)
        self.location = 'home'
        self.commands = command.Command('root')
        self.ghost_commands = command.Command('ghost')
        self.nodes_online = {}
        self.master_node = ''

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
            self.master_node = self.uuid
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
        self.discovery_channel = broadcastchannel.BroadcastChannel(self, 'discovery')
        self.discovery_channel.add_listener(self.discovery_listener)
        self.config_channel = broadcastchannel.BroadcastChannel(self, 'config')
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
            self.ping_nodes()
            try:
                self.location = self.config['locations'][self.hostname]
            except Exception as e:
                pass

        # Show if we are in debug mode
        if self.config['core']['debug']:
            print("Debug mode activated")

        # Create request & response channels
        self.request_channel = broadcastchannel.BroadcastChannel(self, 'request')
        self.request_channel.add_listener(self.request_listener)
        self.response_channel = broadcastchannel.BroadcastChannel(self, 'response')
        self.response_channel.add_listener(self.response_listener)

        # Create messaging channels
        self.message_channel = broadcastchannel.BroadcastChannel(self, 'message')
        self.message_channel.add_listener(self.message_listener)

        # proximity stuff
        self.proximity_channel = broadcastchannel.BroadcastChannel(self, 'proximity')
        self.proximity_channel.add_listener(self.proximity_listener)

        # publish our nodes_online list and start the loop
        self.master_send_nodes_online()

        # Load plugins
        path = os.path.join(os.path.dirname(__file__), 'plugin')
        plugin.Factory.find_plugins(path)

    # plugin methods
    def load_plugin(self, name):
        try:
            print("Loading plugin '%s'" % (name))
            c = plugin.Factory.get_plugin_class(name)
            self.instantiate_plugin(c)
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
            self.instantiate_plugin(c)
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
                self.instantiate_plugin(c)
            else:
                output += (" -%s" % (c.name))

        if self.config['core']['debug']:
            print(output)

    def instantiate_plugin(self, cls):
        p = cls(self, cls.descriptor)
        self.plugins.append(p)

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

            # register node in nodes_online
            args = [s.encode('utf-8').strip() for s in msg]
            args = filter(lambda s: s != '', args)
            self.nodes_online[args[2]] = args[1]

            # Broadcast configuration if master
            if self.master:
                self.config_channel.send(self.config)
                self.discovery_channel.send(['nodes_online', self.nodes_online, self.uuid])
            # Broadcast command list
            for p in self.plugins:
                self.discovery_channel.send(['commands', p.commands.serialize()])

        elif msg[0] == 'ping':
            self.discovery_channel.send(['pong', self.hostname, self.uuid])

        elif msg[0] == 'commands':
            self.ghost_commands.add_subcommand(command.Command.deserialize(msg[1]))

        elif msg[0] == 'nodes_online':
            if not self.master:
                args = self.utils.convert_from_unicode(msg)
                self.master_node = args[2]
                self.nodes_online = args[1]
                print("(slave) recieved online nodes %s" % self.nodes_online)

        elif msg[0] == 'pong':
            args = [s.encode('utf-8').strip() for s in msg]
            args = filter(lambda s: s != '', args)
            self.nodes_online[args[2]] = args[1]

        elif msg[0] == 'byebye':
            try:
                self.nodes_online.pop(msg[2])
            except KeyError:
                pass

        elif msg[0] == 'shutdown':
            self.terminate()

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

        # FIXME todo
        # rawdata = self.commands.serialize()
        # test_command = Command.deserialize(rawdata)
        # print(test_command.list())

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

    def ping_nodes(self):
        if self.master:
            self.discovery_channel.send(['ping', self.hostname, self.uuid])

    def master_send_nodes_online(self):
        if self.master:
            print("(master) sending online nodes list: %s" % (self.nodes_online))
            self.discovery_channel.send(['nodes_online', self.nodes_online, self.uuid])
            self.add_timeout(self.config['core']['sleeptimeout'], self.master_ping_nodes)

    def master_ping_nodes(self):
        if self.master:
            print("(master) pinging nodes. timeout: %s" % (self.config['core']['pingtimeout']))
            self.nodes_online = {}
            self.ping_nodes()
            self.add_timeout(self.config['core']['pingtimeout'], self.master_send_nodes_online)
