
import os
import json
import pika
import socket
import time
import sys
import uuid
import copy
import getpass
import threading
import subprocess
import Queue
import time
import atexit
import logging, logging.handlers
import signal

import plugin
import config
import command
import broadcastchannel
import proximitystatus
import jamesutils
import jamesmessage

# also pika hack
# import logging
# logging.basicConfig()
# https://pika.readthedocs.org/en/latest/connecting.html

# Pika SUPER HACK (c) westlicht
try:
    pika.adapters.blocking_connection.log
except AttributeError:
    class PikaLogDummy(object):
        def debug(*args):
            pass
    pika.adapters.blocking_connection.log = PikaLogDummy()

class PluginNotFound(Exception):
    pass
class BrokerConfigNotLoaded(Exception):
    pass
class AddTimeoutHandlerMissing(Exception):
    pass

class Timeout():
    """Timeout class using ALARM signal."""
    class Timeout(Exception):
        pass
 
    def __init__(self, sec):
        self.sec = sec
 
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.raise_timeout)
        signal.alarm(self.sec)
 
    def __exit__(self, *args):
        signal.alarm(0)    # disable alarm
 
    def raise_timeout(self, *args):
        raise Timeout.Timeout()

class ThreadedCore(threading.Thread):
    def __init__(self, passive = False):
        super(ThreadedCore, self).__init__()
        self.core = Core(passive, False)
        self.utils = jamesutils.JamesUtils(self.core)
        self.internalLogger = self.utils.getLogger('ThreadedCore', self.core.logger)
        self.internalLogger.info('Initialized')

    def get_logger(self, name):
        return self.utils.getLogger('ext_' + name, self.core.logger)

    def work(self):
        self.internalLogger.info('Starting to run loop')
        self.core.run()

    def run(self):
        self.on_exit(self.work())

    def terminate(self):
        self.internalLogger.info('Terminating')
        self.core.add_timeout(0, self.core.terminate)

    def on_exit(self, result):
        return result

class Core(object):

    def __init__(self, passive = False, catchSignals = True):
        self.plugins = []
        self.timeouts = []
        self.timeout_queue = Queue.Queue()
        self.terminated = False
        self.returncode = 0
        self.hostname = socket.getfqdn().split('.')[0].lower()
        self.startup_timestamp = time.time()
        self.utils = jamesutils.JamesUtils(self)
        self.master = False
        self.passive = False
        self.uuid = str(uuid.uuid1())
        self.location = 'home'
        self.proximity_status = proximitystatus.ProximityStatus(self)
        self.persons_status = {}
        self.commands = command.Command('root')
        self.data_commands = command.Command('data')
        self.ghost_commands = command.Command('ghost')
        self.nodes_online = {}
        self.master_node = ''
        self.proximity_state_file = os.path.join(os.path.expanduser("~"), ".james_proximity_state")
        self.stats_file = os.path.join(os.path.expanduser("~"), ".james_stats")
        self.core_lock = threading.RLock()
        self.logger = self.utils.getLogger('%s.%s' % (self.hostname, int(time.time() * 100)))
        self.logger.setLevel(logging.DEBUG)

        self.loadedState = {}
        try:
            file = open(self.stats_file, 'r')
            self.loadedState = self.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
            if self.config['core']['debug']:
                self.logger.debug("Loading states from %s" % (self.stats_file))
        except Exception:
            pass

        atexit.register(self.terminate)

        # setting up pika loggers
        # pika.base_connection.logger = self.utils.getLogger('pika.adapters.base_connection', None)
        # pika.base_connection.logger.setLevel(logger.INFO)
        # pika.blocking_connection.logger = self.utils.getLogger('pika.adapters.blocking_connection', None)
        # pika.blocking_connection.LOGGER.setLevel(logger.INFO)

        try:
            self.os_username = getpass.getuser()
        except Exception as e:
            self.os_username = None
            pass

        # this block can be removed once all the needed signals are registred
        # ignored_signals = ['SIGCLD', 'SIGCHLD', 'SIGTSTP', 'SIGCONT', 'SIGWINCH', 'SIG_IGN', 'SIGPIPE']
        # for i in [x for x in dir(signal) if x.startswith("SIG")]:
        #     try:
        #         if i not in ignored_signals:
        #             signal.signal(getattr(signal,i),self.sighandler)
        #     except RuntimeError,m:
        #         pass
        #     except ValueError,m:
        #         pass

        # catching signals
        self.signal_names = dict((k, v) for v, k in signal.__dict__.iteritems() if v.startswith('SIG'))
        if catchSignals:
            signal.signal(signal.SIGINT,self.on_kill_sig)
            signal.signal(signal.SIGTERM,self.on_kill_sig)
            signal.signal(signal.SIGQUIT,self.on_kill_sig)
            signal.signal(signal.SIGTSTP,self.on_kill_sig)
            signal.signal(signal.SIGSEGV,self.on_fault_sig)


        # Load broker configuration
        try:
            self.brokerconfig = config.YamlConfig("../config/broker.yaml").get_values()
        except Exception as e:
            raise BrokerConfigNotLoaded()

        # Load master configuration
        self.config = None

        try:
            self.config = config.YamlConfig("../config/config.yaml").get_values()
            self.master = True
            mode_output = "master"
            self.master_node = self.uuid
            if not self.config['core']['debug']:
                self.logger.debug('Setting loglevel to INFO')
                self.logger.setLevel(logging.INFO)
        except Exception as e:
            mode_output = "client"

        # check for passive mode
        if passive:
            self.master = False
            self.config = None
            self.passive = True
            mode_output = "passive"

        # Show welcome header
        self.logger.debug("JamesII starting up (%s mode)" % (mode_output))

        # Create global connection
        connected = False
        try:
            cred = pika.PlainCredentials(self.brokerconfig['user'], self.brokerconfig['password'])
            with Timeout(180):
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(host = self.brokerconfig['host'],
                                                                                    port = self.brokerconfig['port'],
                                                                                    virtual_host = self.brokerconfig['vhost'],
                                                                                    credentials = cred,
                                                                                    heartbeat_interval = 30))
            connected = True
        except Exception as e:
            self.logger.warning("Could not connect to RabbitMQ server on default port! %s" % e)

        # Create global connection on fallback port
        if not connected:
            try:
                cred = pika.PlainCredentials(self.brokerconfig['user'], self.brokerconfig['password'])
                with Timeout(180):
                    self.connection = pika.BlockingConnection(pika.ConnectionParameters(host = self.brokerconfig['host'],
                                                                                        port = self.brokerconfig['fallbackport'],
                                                                                        virtual_host = self.brokerconfig['vhost'],
                                                                                        credentials = cred,
                                                                                        heartbeat_interval = 30))
            except Exception as e:
                self.logger.critical("Could not connect to RabbitMQ server on default and fallback port. Exiting! %s" % e)
                sys.exit(2)

        # Create discovery & configuration channels
        self.discovery_channel = broadcastchannel.BroadcastChannel(self, 'discovery')
        self.discovery_channel.add_listener(self.discovery_listener)
        self.config_channel = broadcastchannel.BroadcastChannel(self, 'config')
        self.config_channel.add_listener(self.config_listener)

        # Send hello
        self.discovery_channel.send(['hello', self.hostname, self.uuid])

        # Wait for configuration if not master
        if not self.master:
            self.logger.debug("Waiting for config")
            while not self.config:
                try:
                    self.connection.process_data_events()
                except KeyboardInterrupt:
                    self.logger.warning("Keyboard interrupt detected. Exiting...")
                    sys.exit(3)
                    pass

        # set some stuff that would be triggered by getting config.
        # this is probably not nicely done.
        else:
            self.ping_nodes()
            try:
                self.location = self.config['locations'][self.hostname]
            except Exception as e:
                pass

        # registring network logger handlers
        if self.config['netlogger']['nodes']:
            for target_host in self.config['netlogger']['nodes']:
                self.logger.debug('Adding NetLogger host %s:%s' % (target_host, logging.handlers.DEFAULT_TCP_LOGGING_PORT))
                socketHandler = logging.handlers.SocketHandler(target_host, logging.handlers.DEFAULT_TCP_LOGGING_PORT)
                socketHandler.setLevel(logging.DEBUG)
                self.logger.addHandler(socketHandler)

        self.logger.debug("%s@%s; %s; %s; %s; %s:%s" % (self.hostname,
                                                        self.location,
                                                        self.uuid,
                                                        self.os_username,
                                                        self.master,
                                                        self.brokerconfig['host'], self.brokerconfig['port']))

        self.logger.debug("RabbitMQ: Create request & response channels")
        self.request_channel = broadcastchannel.BroadcastChannel(self, 'request')
        self.request_channel.add_listener(self.request_listener)
        self.response_channel = broadcastchannel.BroadcastChannel(self, 'response')
        self.response_channel.add_listener(self.response_listener)

        self.logger.debug("RabbitMQ: Create messaging channel")
        self.message_channel = broadcastchannel.BroadcastChannel(self, 'message')
        self.message_channel.add_listener(self.message_listener)

        self.logger.debug("RabbitMQ: Create proximity channel")
        self.proximity_channel = broadcastchannel.BroadcastChannel(self, 'proximity')
        self.proximity_channel.add_listener(self.proximity_listener)

        self.logger.debug("RabbitMQ: Create persons_status channel")
        self.persons_status_channel = broadcastchannel.BroadcastChannel(self, 'persons_status')
        self.persons_status_channel.add_listener(self.persons_status_listener)

        self.logger.debug("RabbitMQ: Create dataRequest & dataResponse channels")
        self.data_request_channel = broadcastchannel.BroadcastChannel(self, 'dataRequest')
        self.data_request_channel.add_listener(self.data_request_listener)
        self.data_response_channel = broadcastchannel.BroadcastChannel(self, 'dataResponse')
        self.data_response_channel.add_listener(self.data_response_listener)

        try:
            file = open(self.proximity_state_file, 'r')
            self.proximity_status.status[self.location] = self.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
            if self.config['core']['debug']:
                self.logger.debug("Loading proximity status from %s" % (self.proximity_state_file))
        except IOError:
            pass
        except ValueError:
            pass

        self.logger.debug("Publishing nodes_online list and starting loop")
        self.master_send_nodes_online()

        # Load plugins
        path = os.path.join(os.path.dirname(__file__), 'plugin')

        self.logger.debug("Loading plugins from: %s" % path)
        (loaded_plugins, plugin_warnings, plugin_descr_error) = plugin.Factory.find_plugins(path)

        self.logger.debug('Plugins available: %s' % len(loaded_plugins))
        for (plugin_name, plugin_error) in plugin_warnings:
            self.logger.debug('Plugin %s unavailable: %s' % (plugin_name, str(plugin_error)))
        for plugin_name in plugin_descr_error:
            self.logger.error('Plugin %s has no valid descriptor' % plugin_name)

    # plugin methods
    def load_plugin(self, name):
        try:
            self.logger.debug("Loading plugin '%s'" % (name))
            c = plugin.Factory.get_plugin_class(name)
            self.instantiate_plugin(c)
        except plugin.PluginNotAvailable, e:
            self.logger.warning(e)

    def autoload_plugins(self):

        manual_plugins = []
        for c in plugin.Factory.enum_plugin_classes_with_mode(plugin.PluginMode.MANUAL):
            manual_plugins.append(c.name)
        self.logger.debug("Ignoring manual plugins: %s" % ', '.join(manual_plugins))


        autoloaded_plugins = []
        for c in plugin.Factory.enum_plugin_classes_with_mode(plugin.PluginMode.AUTOLOAD):
            autoloaded_plugins.append(c.name)
            self.instantiate_plugin(c)
        self.logger.debug("Autoloading plugins: %s" % ', '.join(autoloaded_plugins))

        # output = "Loading managed plugins:"
        loaded_managed_plugins = []
        for c in plugin.Factory.enum_plugin_classes_with_mode(plugin.PluginMode.MANAGED):
            load_plugin = False

            try:
                for mp in self.config[c.name]['nodes']:
                    if mp == self.hostname:
                        load_plugin = True
            except KeyError:
                pass
            except TypeError:
                pass

            if load_plugin:
                loaded_managed_plugins.append(c.name)
                self.instantiate_plugin(c)

        self.logger.debug("Loading managed plugins: %s" % ', '.join(loaded_managed_plugins))

    def instantiate_plugin(self, cls):
        p = cls(self, cls.descriptor)
        self.plugins.append(p)

    # command channel methods
    def send_request(self, uuid, name, body, host, plugin):
        """Sends a request."""
        self.add_timeout(0, self.request_channel.send, {'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})
        # self.request_channel.send({'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})

    def send_response(self, uuid, name, body, host, plugin):
        self.add_timeout(0, self.response_channel.send, {'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})
        # self.response_channel.send({'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})

    def request_listener(self, msg):
        for p in self.plugins:
            p.process_command_request_event(msg)
            p.handle_request(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    def response_listener(self, msg):
        for p in self.plugins:
            p.process_command_response_event(msg)
            p.handle_response(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    # data channel methods
    def send_data_request(self, uuid, name, body, host, plugin):
        """Sends a data request."""
        self.add_timeout(0, self.data_request_channel.send, {'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})
        # self.data_request_channel.send({'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})

    def send_data_response(self, uuid, name, body, host, plugin):
        self.add_timeout(0, self.data_response_channel.send, {'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})
        # self.data_response_channel.send({'uuid': uuid, 'name': name, 'body': body, 'host': host, 'plugin': plugin})

    def data_request_listener(self, msg):
        for p in self.plugins:
            p.process_data_request_event(msg)
            p.handle_data_request(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    def data_response_listener(self, msg):
        for p in self.plugins:
            p.process_data_response_event(msg)
            p.handle_data_response(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    def data_listener(self, dataStream):
        """
        Listener for data streams. Calls process_data_response() on each started plugin.
        """
        for p in self.plugins:
            p.process_data_response(dataStream)

    # configuration & config channel methods
    def discovery_listener(self, msg):
        """Manages the discovery channel messages."""
        if msg[0] == 'hello':
            """This host just joined us."""
            show_message = True
            try:
                if not self.config['core']['debug']:
                    show_message = False
            except TypeError as e:
                pass

            # register node in nodes_online
            args = self.utils.list_unicode_cleanup(msg)
            self.nodes_online[args[2]] = args[1]
            if self.master:
                self.logger.debug('New node (%s) detected' % args[1])

            # Broadcast configuration if master
            if self.master:
                self.config_channel.send((self.config, self.uuid))
                self.discovery_channel.send(['nodes_online', self.nodes_online, self.uuid])
                # Send actual proximity state
                # self.publish_proximity_status(self.proximity_status.get_all_status_copy(), 'core')
            # Broadcast command list
            for p in self.plugins:
                if p.commands:
                    self.discovery_channel.send(['commands', p.commands.serialize()])

        elif msg[0] == 'ping':
            """We received a ping request. Be a good boy and send a pong."""
            if not self.master:
                self.logger.debug('Node ping received, sending pong')
            self.discovery_channel.send(['pong', self.hostname, self.uuid])

        elif msg[0] == 'commands':
            """We received new commands. Save them locally."""
            # self.logger.debug('Node commands received')
            self.ghost_commands.merge_subcommand(command.Command.deserialize(msg[1]))

        elif msg[0] == 'nodes_online':
            """We received a new nodes_online list. Replace our current one."""
            if not self.master:
                args = self.utils.convert_from_unicode(msg)
                self.master_node = args[2]
                if self.nodes_online != args[1]:
                    self.logger.debug('Updating online nodes from master')
                self.nodes_online = args[1]

        elif msg[0] == 'pong':
            """We received a pong. We will save this host in nodes_online."""
            args = self.utils.list_unicode_cleanup(msg)
            self.nodes_online[args[2]] = args[1]

        elif msg[0] == 'byebye':
            """This host is shutting down. Remove him from nodes_online."""
            try:
                self.nodes_online.pop(msg[2])
                if self.master:
                    self.logger.debug('Node (%s) is now offline' % msg[1])
            except KeyError:
                pass

        elif msg[0] == 'shutdown':
            """We received a systemwide shutdown signal. So STFU and RAGEQUIT!"""
            self.logger.debug('We received a systemwide shutdown signal. So STFU and RAGEQUIT!')
            self.terminate()

        for p in self.plugins:
            """Call process_discovery_event() on each started plugin."""
            p.process_discovery_event(msg)

    def config_listener(self, (new_config, sender_uuid)):
        """
        Listens for configurations on the configuration channel. If we get a
        changed version of the config (= new config on master node) we will exit.
        """
        if not self.config:
            try:
                if not new_config['core']['debug']:
                    self.logger.debug('Setting loglevel to INFO')
                    self.logger.setLevel(logging.INFO)
            except TypeError as e:
                pass

            self.logger.debug("Received config")

            self.config = new_config
            self.master_node = sender_uuid

            try:
                self.location = self.utils.convert_from_unicode(self.config['locations'][self.hostname])
            except Exception as e:
                self.location = 'home'
        else:
            if self.config != new_config:
                self.logger.info("The configuration file has changed. Exiting!")
                self.terminate()
            elif self.master_node != sender_uuid:
                self.logger.info("The master node has changed.")
                self.master_node = sender_uuid

    # message channel methods
    def send_message(self, msg):
        """
        Sends a message over the message channel.
        """
        self.message_channel.send(msg)

    def new_message(self, name = "uninitialized_message"):
        """
        Returns a new instance of JamesMessage.
        """
        return jamesmessage.JamesMessage(self, name)

    def message_listener(self, msg):
        """
        Listener for messages. Calls process_message() on each started plugin.
        """
        message = jamesmessage.JamesMessage(self, "received message")
        message.set(msg)
        
        for p in self.plugins:
            p.process_message(message)

    # persons_status channel methods
    def persons_status_listener(self, msg):
        """
        Listens to persons_status changes on the persons_status channel and
        update the local storage.
        """
        if msg['location'] == self.location:
            self.logger.debug("Recieved persons_status update: %s. Saving it to core." % msg['persons_status'])
            self.persons_status = self.utils.convert_from_unicode(msg['persons_status'])

    def send_persons_status(self, persons_status, pluginname):
        """
        Call the distribution methon for persons states
        """
        self.add_timeout(0, self.publish_persons_status_callback, persons_status, pluginname)

    def publish_persons_status_callback(self, persons_status, pluginname):
        """
        send the persons states over the persons_status channel.
        """
        self.logger.debug('Publishing persons status update %s from plugin %s' % (persons_status, pluginname))
        try:
            self.persons_status_channel.send({'persons_status' : persons_status,
                                              'host' : self.hostname,
                                              'plugin' : pluginname,
                                              'location' : self.location})
        except Exception as e:
            self.logger.warning("Could not send persons status (%s)" % (e))    

    # proximity channel methods
    def proximity_listener(self, msg):
        """
        Listens to proximity status changes on the proximity channel and
        update the local storage. Calls process_proximity_event() on all
        started plugins.
        """
        try:
            self.logger.debug("core.proximity_listener: %s" % msg)
            oldState = self.proximity_status.get_status_here()
            self.proximity_status.update_all_status(msg['status'], msg['plugin'])
            if msg['status'][self.location] != oldState:
                self.logger.debug("Recieved proximity update (listener). Calling process_proximity_event on plugins.")
                for p in self.plugins:
                    p.process_proximity_event(msg)
        except KeyError:
            # this proximity event is not for our location. just ignore it for now
            pass

    def proximity_event(self, changedstatus, pluginname):
        """
        If the local proximity state has changed, call the publish method
        """
        newstatus = {}
        oldstatus = self.proximity_status.get_all_status_copy()

        if oldstatus[self.location] != changedstatus:
            newstatus[self.location] = changedstatus
        else:
            newstatus[self.location] = oldstatus[self.location]
        self.logger.debug("publish_proximity_status: %s from %s" % (newstatus, pluginname))
        self.publish_proximity_status(newstatus, pluginname)

    def publish_proximity_status(self, newstatus, pluginname):
        self.add_timeout(0, self.publish_proximity_status_callback, newstatus, pluginname)

    def publish_proximity_status_callback(self, newstatus, pluginname):
        """
        send the newstatus proximity status over the proximity channel.
        """
        self.logger.debug("Publishing proximity status update %s from plugin %s" % (newstatus, pluginname))
        try:
            self.proximity_channel.send({'status' : newstatus,
                                         'host' : self.hostname,
                                         'plugin' : pluginname,
                                         'location' : self.location})
        except Exception as e:
            self.logger.warning("Could not send proximity status (%s)" % (e))

    # discovery methods
    def ping_nodes(self):
        """
        If master, ping send the ping command to the discovery channel
        """
        if self.master:
            self.logger.debug('Pinging slave nodes.')
            self.discovery_channel.send(['ping', self.hostname, self.uuid])

    def master_send_nodes_online(self):
        """
        If master, sends the nodes_online over the discovery channel. Registers
        master_ping_nodes() callback after given sleeptimeout in config.
        """
        if self.master:
            nodes_online = []
            for node in self.nodes_online.keys():
                nodes_online.append(self.nodes_online[node])
            self.logger.debug('Publishing online nodes: %s' % nodes_online)

            self.discovery_channel.send(['nodes_online', self.nodes_online, self.uuid])
            self.add_timeout(self.config['core']['sleeptimeout'], self.master_ping_nodes)

    def master_ping_nodes(self):
        """
        If master, calls the ping_nodes() method and registers master_send_nodes_online()
        after given pingtimeout in config.
        """
        if self.master:
            self.nodes_online = {}
            self.ping_nodes()
            self.add_timeout(self.config['core']['pingtimeout'], self.master_send_nodes_online)

    # base methods
    def run(self):
        """
        This method is called right at the beginning of normal operations. (after initialisation)
        Calls start() on all started plugins.
        """
        # Broadcast command list
        for p in self.plugins:
            if p.commands:
                self.discovery_channel.send(['commands', p.commands.serialize()])

        if self.passive:
            self.logger.debug(time.strftime("JamesII Ready on %A the %d of %B at %H:%M:%S", time.localtime()))
        else:
            self.logger.info(time.strftime("JamesII Ready on %A the %d of %B at %H:%M:%S", time.localtime()))
        for p in self.plugins:
            p.start()

        while not self.terminated:
            try:
                with Timeout(180):
                    self.lock_core()
                with Timeout(180):
                    self.connection.process_data_events()
                with Timeout(180):
                    self.process_timeouts()
                with Timeout(180):
                    self.unlock_core()
                    #self.logger.debug("process events")
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt detected. Exiting...")
                self.terminate(3)
            except pika.exceptions.ChannelClosed:
                # channel closed error
                self.logger.critical("Lost connection to RabbitMQ server! (ChannelClosed)")
                self.terminate(2)
            except pika.exceptions.ConnectionClosed:
                # connection closed error
                self.logger.critical("Lost connection to RabbitMQ server! (ConnectionClosed)")
                self.terminate(2)
            except pika.exceptions.AMQPConnectionError:
                # disconnection error
                self.logger.critical("Lost connection to RabbitMQ server! (AMQPConnectionError)")
                self.terminate(2)
            except Timeout.Timeout:
                self.logger.critical("Detected hanging core. Exiting...")
                self.terminate(2)

            #if i hang with threads or subthreads or stuff, comment the following block!
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = exc_tb.tb_frame.f_code.co_filename
                self.logger.critical("Exception in core loop: %s in %s:%s %s" % (e, fname, exc_tb.tb_lineno, exc_type))
                self.terminate(1)

        self.logger.debug("Exiting with returncode (%s)" % self.returncode)
        sys.exit(self.returncode)

    def lock_core(self):
        self.core_lock.acquire()
    
    def unlock_core(self):
        self.core_lock.release()

    def terminate(self, returncode = 0):
        """
        Terminate the core. This method will first call the terminate() on each plugin.
        """
        if not self.terminated:
            self.returncode = returncode
            self.logger.debug("Core.terminate() called. I shall die now.")

            try:
                self.discovery_channel.send(['byebye', self.hostname, self.uuid])
            except Exception:
                pass

            saveStats = {}
            for p in self.plugins:
                saveStats[p.name] = p.safe_state()
            try:
                file = open(self.stats_file, 'w')
                file.write(json.dumps(saveStats))
                file.close()
                self.logger.debug("Saving stats to %s" % (self.stats_file))
            except IOError:
                if self.passive:
                    self.logger.debug("Could not safe stats to file")
                else:
                    self.logger.warning("Could not safe stats to file")

            for p in self.plugins:
                p.terminate()
            try:
                file = open(self.proximity_state_file, 'w')
                file.write(json.dumps(self.proximity_status.status[self.location]))
                file.close()
                self.logger.debug("Saving proximity status to %s" % (self.proximity_state_file))
            except IOError:
                if self.passive:
                    self.logger.debug("Could not safe proximity status to file")
                else:
                    self.logger.warning("Could not safe proximity status to file")
            except KeyError:
                # no proximity state found for this location
                pass
            self.terminated = True

    # threading methods
    class Timeout(object):
        def __init__(self, seconds, handler, args, kwargs):
            self.seconds = seconds
            self.deadline = time.time() + seconds
            self.handler = handler
            self.args = args
            self.kwargs = kwargs

    def add_timeout(self, seconds, handler, *args, **kwargs):
        if not handler:
            raise AddTimeoutHandlerMissing()

        self.timeout_queue.put(Core.Timeout(seconds, handler, args, kwargs))

    def process_timeouts(self):
        # Copy timeouts from queue to local list
        while True:
            try:
                timeout = self.timeout_queue.get_nowait()
                self.timeouts.append(timeout)
            except Queue.Empty:
                break
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = exc_tb.tb_frame.f_code.co_filename
                self.logger.critical("Exception 1 in process_timeouts: %s in %s:%s %s" % (e, fname, exc_tb.tb_lineno, exc_type))

        # Process events
        try:
            now = time.time()
            for timeout in self.timeouts:
                if timeout.deadline <= now:
                    self.logger.debug('Processing timeout %s' % timeout.handler)
                    timeout.handler(*timeout.args, **timeout.kwargs)
            self.timeouts = filter(lambda t: t.deadline > now, self.timeouts)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = exc_tb.tb_frame.f_code.co_filename
            self.logger.critical("Exception 2 in process_timeouts: %s in %s:%s %s" % (e, fname, exc_tb.tb_lineno, exc_type))

    def spawnSubprocess(self, target, onExit, target_args = None, logger = None):
        """
        Spawns a subprocess with call target and calls onExit with the return
        when finished
        """
        if not logger:
            logger = self.logger
        logger.debug('Spawning subprocess (%s)' % target)
        def runInThread(target, onExit, target_args):
            if target_args != None:
                self.logger.debug('Ending subprocess (%s)' % target)
                self.add_timeout(0, onExit, target(target_args))
            else:
                self.logger.debug('Ending subprocess (%s)' % target)
                self.add_timeout(0, onExit, target())

        thread = threading.Thread(target=runInThread, args=(target, onExit, target_args))
        thread.start()
        return thread

    # signal handlers
    def on_kill_sig(self, signal, frame):
        self.logger.info("%s detected. Exiting..." % self.signal_names[signal])
        self.terminate(3)

    def on_fault_sig(self, signal, frame):
        self.logger.info("%s detected. Exiting..." % self.signal_names[signal])
        self.terminate(1)

    # catchall handler
    # def sighandler(self, signal, frame):
    #     self.logger.warning("Uncatched signal %s (%s)" % (self.signal_names[signal], signal))

    #     message = self.new_message('sighandler')
    #     message.level = 2
    #     message.header = "Uncaught SIGNAL detected on %s: %s (%s)" % (self.hostname, self.signal_names[signal], signal)
    #     message.send()

