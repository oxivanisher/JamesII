import atexit
import getpass
import json
import logging
import logging.handlers
import os
import queue
import signal
import socket
import sys
import threading
import time
import uuid

import pika

from . import broadcastchannel
from . import command
from . import config
from . import jamesmessage
from . import jamesutils
from . import plugin
from . import presence

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


class Timeout:
    """Timeout class using ALARM signal."""

    class Timeout(Exception):
        pass

    def __init__(self, sec):
        self.sec = sec

    def __enter__(self):
        # Fixme: Windows has no support for signal.SIGALRM
        if os.name == 'posix':
            signal.signal(signal.SIGALRM, self.raise_timeout)
            signal.alarm(self.sec)

    def __exit__(self, *args):
        # Fixme: Windows has no support for signal.SIGALRM
        if os.name == 'posix':
            signal.alarm(0)  # disable alarm

    def raise_timeout(self, *args):
        raise Timeout.Timeout()


class ThreadedCore(threading.Thread):
    def __init__(self, passive=False):
        super(ThreadedCore, self).__init__()
        self.core = Core(passive, False)
        self.utils = jamesutils.JamesUtils(self.core)
        self.internalLogger = self.utils.get_logger('ThreadedCore', self.core.logger)
        self.internalLogger.info('Initialized')
        self.name = "ThreadedCore: %s" % self.__class__.__name__

    def get_logger(self, name):
        return self.utils.get_logger('ext_' + name, self.core.logger)

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

    def __init__(self, passive=False, catch_signals=True):
        self.plugins = []
        self.timeouts = []
        self.timeout_queue = queue.Queue()
        self.terminated = False
        self.terminating = False
        self.return_code = 0
        self.startup_timestamp = time.time()
        self.utils = jamesutils.JamesUtils(self)
        self.master = False
        self.passive = False
        self.uuid = str(uuid.uuid1())
        self.location = 'home'
        self.presences = presence.Presences(self)
        self.no_alarm_clock_data = {}
        self.events_today = {}
        self.commands = command.Command('root')
        self.data_commands = command.Command('data')
        self.ghost_commands = command.Command('ghost')
        self.nodes_online = {}
        self.master_node = ''
        self.presences_file = os.path.join(os.path.expanduser("~"), ".james_presences")
        self.stats_file = os.path.join(os.path.expanduser("~"), ".james_stats")
        self.system_messages_file = os.path.join(os.path.expanduser("~"), ".james_system_messages")
        self.core_lock = threading.RLock()
        self.rabbitmq_channels = []

        # Load broker configuration here, in case the hostname has to be specified
        try:
            self.broker_config = config.YamlConfig("../config/broker.yaml").get_values()
        except Exception as e:
            raise BrokerConfigNotLoaded()

        if 'myhostname' in list(self.broker_config.keys()):
            self.hostname = self.broker_config['myhostname']
        else:
            self.hostname = socket.gethostname().lower()

        self.logger = self.utils.get_logger('%s.%s' % (self.hostname, int(time.time() * 100)))
        self.logger.setLevel(logging.DEBUG)

        self.logger.debug(f"JamesII starting up with PID {os.getpid()}")

        self.main_loop_sleep = None
        self._set_main_loop_sleep(True)

        self.loadedState = {}
        try:
            file = open(self.stats_file, 'r')
            self.loadedState = self.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
            self.logger.debug("Loading states from %s" % self.stats_file)

        except Exception:
            self.logger.warning("Unable to load states from %s" % self.stats_file)

        atexit.register(self.terminate)

        try:
            self.os_username = getpass.getuser()
        except Exception as e:
            self.os_username = None
            pass

        # catching signals
        self.signal_names = dict((k, v) for v, k in signal.__dict__.items() if v.startswith('SIG'))
        if catch_signals:
            signal.signal(signal.SIGINT, self.on_kill_sig)
            signal.signal(signal.SIGTERM, self.on_kill_sig)
            signal.signal(signal.SIGSEGV, self.on_fault_sig)
            signal.signal(signal.SIGHUP, self.on_kill_sig)

            # Fixme: Windows has no support for some signals
            if os.name == 'posix':
                signal.signal(signal.SIGQUIT, self.on_kill_sig)
                signal.signal(signal.SIGTSTP, self.on_kill_sig)

        # Load master configuration
        self.config = None

        try:
            self.config = config.YamlConfig("../config/config.yaml").get_values()
            self.master = True
            mode_output = "master"
            self.master_node = self.uuid
            self._set_main_loop_sleep()
            if not self.config['core']['debug']:
                self.logger.debug('Setting loglevel to INFO')
                self.logger.setLevel(logging.INFO)
        except IOError:
            self.logger.info("No configuration file found. Defaulting to client mode.")
            mode_output = "client"
        except Exception as e:
            self.logger.warning("Unable to load config even tough the file exists! %s" % e)
            sys.exit(2)

        # check for passive mode
        if passive:
            self.master = False
            self.config = None
            self.passive = True
            mode_output = "passive"

        # Show welcome header
        self.logger.debug("JamesII %s node %s starting up" % (mode_output, self.hostname))

        # Create global connection
        connected = False
        try:
            cred = pika.PlainCredentials(self.broker_config['user'], self.broker_config['password'])
            with Timeout(300):
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.broker_config['host'],
                                                                                    port=self.broker_config['port'],
                                                                                    virtual_host=self.broker_config[
                                                                                        'vhost'],
                                                                                    credentials=cred))
            connected = True
        except Exception as e:
            self.logger.warning("Could not connect to RabbitMQ server on default port! %s" % e)

        # Create global connection on fallback port
        if not connected:
            try:
                cred = pika.PlainCredentials(self.broker_config['user'], self.broker_config['password'])
                with Timeout(300):
                    self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.broker_config['host'],
                                                                                        port=self.broker_config[
                                                                                            'fallbackport'],
                                                                                        virtual_host=self.broker_config[
                                                                                            'vhost'],
                                                                                        credentials=cred))
            except Exception as e:
                self.logger.critical(
                    "Could not connect to RabbitMQ server on default and fallback port. Exiting! %s" % e)
                sys.exit(2)

        # Create discovery & configuration channels
        self.discovery_channel = broadcastchannel.BroadcastChannel(self, 'discovery')
        self.discovery_channel.add_listener(self.discovery_listener)
        self.config_channel = broadcastchannel.BroadcastChannel(self, 'config')
        self.config_channel.add_listener(self.config_listener)

        # Send hello
        self.lock_core()
        self.discovery_channel.send(['hello', self.hostname, self.uuid])
        self.unlock_core()

        # Wait for configuration if not master
        if not self.master:
            self.logger.debug("Waiting for config")
            while not self.config:
                try:
                    with Timeout(180):
                        self.lock_core()
                        self.connection.process_data_events()
                        self.unlock_core()
                except KeyboardInterrupt:
                    self.logger.warning("Keyboard interrupt detected. Exiting...")
                    sys.exit(3)
                    pass
                except pika.exceptions.ChannelClosed:
                    # channel closed error
                    self.logger.critical("Lost connection to RabbitMQ server! (ChannelClosed)")
                except pika.exceptions.ConnectionClosed:
                    # connection closed error
                    self.logger.critical("Lost connection to RabbitMQ server! (ConnectionClosed)")
                except pika.exceptions.AMQPConnectionError:
                    # disconnection error
                    self.logger.critical("Lost connection to RabbitMQ server! (AMQPConnectionError)")
                except Timeout.Timeout:
                    self.logger.critical("Detected hanging core. Exiting...")

        # set some stuff that would be triggered by getting config.
        # this is probably not nicely done.
        else:
            self.ping_nodes()
            try:
                self.location = self.config['locations'][self.hostname]
            except Exception as e:
                pass

        # registering network logger handlers
        if self.config['netlogger']['nodes']:
            for target_host in self.config['netlogger']['nodes']:
                self.logger.debug(
                    'Adding NetLogger host %s:%s' % (target_host, logging.handlers.DEFAULT_TCP_LOGGING_PORT))
                socketHandler = logging.handlers.SocketHandler(target_host, logging.handlers.DEFAULT_TCP_LOGGING_PORT)
                socketHandler.setLevel(logging.DEBUG)
                self.logger.addHandler(socketHandler)

        self.logger.debug("%s@%s; %s; %s; %s; %s:%s" % (self.hostname,
                                                        self.location,
                                                        self.uuid,
                                                        self.os_username,
                                                        self.master,
                                                        self.broker_config['host'], self.broker_config['port']))

        self.logger.debug("RabbitMQ: Create request & response channels")
        self.request_channel = broadcastchannel.BroadcastChannel(self, 'request')
        self.request_channel.add_listener(self.request_listener)
        self.response_channel = broadcastchannel.BroadcastChannel(self, 'response')
        self.response_channel.add_listener(self.response_listener)

        self.logger.debug("RabbitMQ: Create messaging channel")
        self.message_channel = broadcastchannel.BroadcastChannel(self, 'msg')
        self.message_channel.add_listener(self.message_listener)

        self.logger.debug("RabbitMQ: Create presence channel")
        self.presence_channel = broadcastchannel.BroadcastChannel(self, 'presence')
        self.presence_channel.add_listener(self.presence_listener)

        self.logger.debug("RabbitMQ: Create no_alarm_clock channel")
        self.no_alarm_clock_channel = broadcastchannel.BroadcastChannel(self, 'no_alarm_clock')
        self.no_alarm_clock_channel.add_listener(self.no_alarm_clock_listener)

        self.logger.debug("RabbitMQ: Create events_today channel")
        self.events_today_channel = broadcastchannel.BroadcastChannel(self, 'events_today')
        self.events_today_channel.add_listener(self.events_today_listener)

        self.logger.debug("RabbitMQ: Create dataRequest & dataResponse channels")
        self.data_request_channel = broadcastchannel.BroadcastChannel(self, 'dataRequest')
        self.data_request_channel.add_listener(self.data_request_listener)
        self.data_response_channel = broadcastchannel.BroadcastChannel(self, 'dataResponse')
        self.data_response_channel.add_listener(self.data_response_listener)

        try:
            file = open(self.presences_file, 'r')
            self.presences.load(json.loads(file.read()))
            file.close()
            if self.config['core']['debug']:
                self.logger.debug("Loading presences from %s" % self.presences_file)
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
            self.logger.warning('Plugin %s unavailable: %s' % (plugin_name, str(plugin_error)))
        for plugin_name in plugin_descr_error:
            self.logger.error('Plugin %s has no valid descriptor' % plugin_name)

    # core methods
    def _set_main_loop_sleep(self, initial = False):
        # set initial main loop sleep to a sane value also for very slow nodes
        main_loop_sleep = 0.1
        source = "startup value"

        try:

            if self.passive:
                # load global core setting
                if 'main_loop_sleep_passive' in self.config['core'].keys():
                    source = "system wide passive value"
                    main_loop_sleep = float(self.config['core']['main_loop_sleep_passive'])

            else:
                # load global core setting
                if 'main_loop_sleep' in self.config['core'].keys():
                    source = "system wide value"
                    main_loop_sleep = float(self.config['core']['main_loop_sleep'])

                # load node specific setting
                if 'nodes_main_loop_sleep' in self.config['core'].keys():
                    if self.hostname in self.config['core']['nodes_main_loop_sleep'].keys():
                        source = "node specific value"
                        main_loop_sleep = float(self.config['core']['nodes_main_loop_sleep'][self.hostname])

        except Exception:
            pass

        if self.main_loop_sleep != main_loop_sleep:
            if not initial:
                self.logger.info("Set main loop sleep to %s from %s" % (main_loop_sleep, source))
            self.main_loop_sleep = main_loop_sleep

    # plugin methods
    def load_plugin(self, name):
        try:
            self.logger.debug("Loading plugin '%s'" % name)
            c = plugin.Factory.get_plugin_class(name)
            self.instantiate_plugin(c)
        except plugin.PluginNotAvailable as e:
            self.logger.warning(e)

    def autoload_plugins(self):

        manual_plugins = []
        for c in plugin.Factory.enum_plugin_classes_with_mode(plugin.PluginMode.MANUAL):
            manual_plugins.append(c.name)
        self.logger.debug("Ignoring manual plugins: %s" % ', '.join(manual_plugins))

        autoload_plugins = []
        for c in plugin.Factory.enum_plugin_classes_with_mode(plugin.PluginMode.AUTOLOAD):
            autoload_plugins.append(c.name)
            self.instantiate_plugin(c)
        self.logger.debug("Autoloading plugins: %s" % ', '.join(autoload_plugins))

        # output = "Loading managed plugins:"
        managed_plugins = []
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
                managed_plugins.append(c.name)
                self.instantiate_plugin(c)

        self.logger.debug("Loading managed plugins: %s" % ', '.join(managed_plugins))

    def instantiate_plugin(self, cls):
        p = cls(self, cls.descriptor)
        self.plugins.append(p)

    # command channel methods
    def send_request(self, my_uuid, name, body, host, my_plugin):
        """Sends a request."""
        self.add_timeout(0, self.request_channel.send,
                         {'uuid': my_uuid, 'name': name, 'body': body, 'host': host, 'plugin': my_plugin})

    def send_response(self, my_uuid, name, body, host, my_plugin):
        self.add_timeout(0, self.response_channel.send,
                         {'uuid': my_uuid, 'name': name, 'body': body, 'host': host, 'plugin': my_plugin})

    def request_listener(self, msg):
        for p in self.plugins:
            p.process_command_request_event(msg)
            p.handle_request(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    def response_listener(self, msg):
        for p in self.plugins:
            p.process_command_response_event(msg)
            p.handle_response(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    # data channel methods
    def send_data_request(self, my_uuid, name, body, host, my_plugin):
        """Sends a data request."""
        self.add_timeout(0, self.data_request_channel.send,
                         {'uuid': my_uuid, 'name': name, 'body': body, 'host': host, 'plugin': my_plugin})

    def send_data_response(self, my_uuid, name, body, host, my_plugin):
        self.add_timeout(0, self.data_response_channel.send,
                         {'uuid': my_uuid, 'name': name, 'body': body, 'host': host, 'plugin': my_plugin})

    def data_request_listener(self, msg):
        for p in self.plugins:
            p.process_data_request_event(msg)
            p.handle_data_request(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    def data_response_listener(self, msg):
        for p in self.plugins:
            p.process_data_response_event(msg)
            p.handle_data_response(msg['uuid'], msg['name'], msg['body'], msg['host'], msg['plugin'])

    def data_listener(self, data_stream):
        """
        Listener for data streams. Calls process_data_response() on each started plugin.
        """
        for p in self.plugins:
            p.process_data_response(data_stream)

    # configuration & config channel methods
    def discovery_listener(self, msg):
        """Manages the discovery channel messages."""
        if msg[0] == 'hello':
            """This host just joined us."""

            # register node in nodes_online
            args = self.utils.list_unicode_cleanup(msg)
            self.nodes_online[args[2]] = args[1]
            if self.master:
                self.logger.debug('New node (%s) detected' % args[1])

            # Broadcast configuration if master
            if self.master:
                self.lock_core()
                self.config_channel.send((self.config, self.uuid))
                self.discovery_channel.send(['nodes_online', self.nodes_online, self.uuid])
                self.unlock_core()

                # send current no_alarm_clock value
                self.logger.debug("Sending current no_alarm_clock value")
                for plugin_name in self.no_alarm_clock_data.keys():
                    no_alarm_clock = self.no_alarm_clock_data[plugin_name]
                    self.logger.debug(f"Sending current no_alarm_clock value {no_alarm_clock} for {plugin_name}")
                    self.no_alarm_clock_update(no_alarm_clock, plugin_name)

                # send current events_today value
                self.logger.debug("Sending current events_today value")
                self.events_today_update(self.events_today, 'core')

            # Broadcast command list
            self.logger.debug("Sending command list")
            for p in self.plugins:
                if p.commands:
                    self.lock_core()
                    self.discovery_channel.send(['commands', p.commands])
                    self.unlock_core()

        elif msg[0] == 'ping':
            """We received a ping request. Be a good boy and send a pong."""
            if not self.master:
                self.logger.debug('Node ping received, sending pong')
            self.lock_core()
            self.discovery_channel.send(['pong', self.hostname, self.uuid])
            self.unlock_core()

        elif msg[0] == 'commands':
            """We received new commands. Save them locally."""
            self.ghost_commands.merge_subcommand(msg[1])

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

    def config_listener(self, msg):
        """
        Listens for configurations on the configuration channel. If we get a
        changed version of the config (= new config on master node) we will exit.
        """
        (new_config, sender_uuid) = msg
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
            self._set_main_loop_sleep()

            try:
                self.location = self.utils.convert_from_unicode(self.config['locations'][self.hostname])
            except Exception as e:
                self.location = 'home'
        else:
            if not self.utils.dict_deep_compare(self.config, new_config):
                if self.uuid == sender_uuid == self.master_node:
                    cfg_diff = []
                    for key in list(self.config.keys()):
                        if key not in new_config:
                            cfg_diff.append(key)
                    if len(cfg_diff):
                        self.logger.warning("Somehow, we sent a new config event if we already are the master! "
                                            "There is probably a problem in our config: %s" % (", ".join(cfg_diff)))
                    else:
                        self.logger.debug("Received my own config probably after I sent it because of a node startup.")

                elif self.master:
                    self.logger.warning("I thought I am the master, but things seemed to have changed. Exiting!")
                    self.terminate()
                else:
                    if self.config != new_config:
                        self.logger.warning("Received new config from master. Reloading config on all plugins.")
                        self.config = new_config
                        self._set_main_loop_sleep()
                        for p in self.plugins:
                            p.reload_config()
                    else:
                        self.logger.debug("Received the same config I already have.")
            elif self.master_node != sender_uuid:
                self.logger.info("The master node but not the config has changed.")
                self.master_node = sender_uuid

    # msg channel methods
    def send_message(self, msg):
        """
        Sends a msg over the msg channel.
        """
        self.lock_core()
        self.message_channel.send(msg)
        self.unlock_core()

    def new_message(self, name="uninitialized_message"):
        """
        Returns a new instance of JamesMessage.
        """
        return jamesmessage.JamesMessage(self, name)

    def message_listener(self, msg):
        """
        Listener for messages. Calls process_message() on each started plugin.
        """
        message = jamesmessage.JamesMessage(self, "received msg")
        message.set(msg)

        for p in self.plugins:
            p.process_message(message)

    # presence channel methods
    def presence_listener(self, msg):
        """
        Listens to presence changes on the presence channel and update the local storage.
        Calls process_presence_event() on all started plugins if something changed here.
        """
        self.logger.debug("core.presence_listener: %s" % msg)
        (changed, presence_before, presence_now) = self.presences.process_presence_message(msg)
        if changed:
            self.logger.debug("Received presence update (listener). Calling process_presence_event on plugins.")
            for p in self.plugins:
                p.process_presence_event(presence_before, presence_now)

    def get_present_users_here(self):
        return self.presences.get_present_users_here()

    def is_admin_user_here(self):
        for person in self.get_present_users_here():
            if person in self.config['persons'].keys():
                if 'admin' in self.config['persons'][person].keys():
                    if self.config['persons'][person]['admin']:
                        return True
        return False

    def presence_event(self, plugin_name, users):
        """
        A presence plugin found a change in persons and wants to send this to all nodes
        """
        new_presence = {'location': self.location, 'plugin': plugin_name, 'host': self.hostname, 'users': users}
        self.system_message_add(plugin_name, f"Publish presence change from {self.hostname}@{self.location}: "
                                                     f"[{', '.join(users)}]")
        self.logger.debug(f"publish_presence_event: {new_presence}")
        self.publish_presence_status(new_presence)

    def publish_presence_status(self, new_presence):
        self.add_timeout(0, self.publish_presence_status_callback, new_presence)

    def publish_presence_status_callback(self, new_presence):
        """
        send the new_presence presence over the presence channel.
        """
        self.logger.debug("Publishing presence update %s" % new_presence)
        try:
            self.lock_core()
            self.presence_channel.send(new_presence)
            self.unlock_core()
        except Exception as e:
            self.logger.warning(f"Could not send presence update: {e}")
            self.system_message_add("Core", f"Could not send presence update: {e}")

    # no_alarm_clock channel methods
    def check_no_alarm_clock(self):
        """
        Check all reported plugins. If anyone sent "true", return True.
        """
        for plugin_name in self.no_alarm_clock_data.keys():
            if self.no_alarm_clock_data[plugin_name]:
                return True
        return False

    def no_alarm_clock_listener(self, msg):
        """
        Listens to no_alarm_clock events changes on the no_alarm_clock channel and
        update the local storage.
        """
        self.logger.debug(f"core.no_alarm_clock_listener: {msg}")

        if msg['plugin'] not in self.no_alarm_clock_data.keys():
            self.no_alarm_clock_data[msg['plugin']] = False
        if self.no_alarm_clock_data[msg['plugin']] != msg['events']:
            self.no_alarm_clock_data[msg['plugin']] = msg['events']
            global_alarmclock_str_state = 'disabled' if self.check_no_alarm_clock() else 'enabled'
            plugin_alarmclock_str_state = 'disabled' if msg['events'] else 'enabled'
            self.logger.info(f"Received no_alarm_clock update for {msg['plugin']} to {plugin_alarmclock_str_state} "
                             f"(listener). Global alarm clock is now {global_alarmclock_str_state}.")
            self.no_alarm_clock_data[msg['plugin']] = msg['events']

    def no_alarm_clock_update(self, changed_events, no_alarm_clock_source):
        """
        Always call the publish method
        """
        self.logger.debug("publish_no_alarm_clock_events: %s" % changed_events)
        self.publish_no_alarm_clock_events(changed_events, no_alarm_clock_source)

    def publish_no_alarm_clock_events(self, new_events, no_alarm_clock_source):
        """
        Distribute no_alarm_clock to all nodes
        """
        self.add_timeout(0, self.publish_no_alarm_clock_events_callback, new_events, no_alarm_clock_source)

    def publish_no_alarm_clock_events_callback(self, new_events, no_alarm_clock_source):
        """
        send the new_events no_alarm_clock events over the no_alarm_clock channel.
        """
        self.logger.debug("Publishing no_alarm_clock events update %s from plugin %s" %
                          (new_events, no_alarm_clock_source))
        try:
            self.lock_core()
            self.no_alarm_clock_channel.send({'events': new_events,
                                              'host': self.hostname,
                                              'plugin': no_alarm_clock_source})
            self.unlock_core()
        except Exception as e:
            self.logger.warning("Could not send no_alarm_clock events (%s)" % e)

    # events_today channel methods
    def events_today_listener(self, msg):
        """
        Listens to events_today events changes on the events_today channel and
        update the local storage.
        """
        self.logger.debug("core.events_today_listener: %s" % msg)
        if msg['plugin'] not in self.events_today.keys():
            self.events_today[msg['plugin']] = []
        if sorted(self.events_today[msg['plugin']]) != sorted(msg['events']):
            self.logger.debug(f"Received events_today update (listener). Sender plugin is {msg['plugin']} "
                              f"and new value is {msg['events']}")
            self.events_today[msg['plugin']] = msg['events']

    def events_today_update(self, changed_status, events_today_source):
        """
        Always call the publish method
        """
        self.logger.debug(f"publish_events_today_status from plugin {events_today_source}: {changed_status}")
        self.publish_events_today_events(changed_status, events_today_source)

    def publish_events_today_events(self, new_events, events_today_source):
        """
        Distribute events_today to all nodes
        """
        self.add_timeout(0, self.publish_events_today_events_callback, new_events, events_today_source)

    def publish_events_today_events_callback(self, new_events, events_today_source):
        """
        send the new_events events_today events over the events_today channel.
        """
        self.logger.debug("Publishing events_today events update %s from plugin %s" %
                          (new_events, events_today_source))
        try:
            self.lock_core()
            self.events_today_channel.send({'events': new_events,
                                            'host': self.hostname,
                                            'plugin': events_today_source})
            self.unlock_core()
        except Exception as e:
            self.logger.warning("Could not send events_today events (%s)" % e)

    # discovery methods
    def ping_nodes(self):
        """
        If master, ping send the ping command to the discovery channel
        """
        if self.master:
            self.logger.debug('Pinging slave nodes.')
            self.lock_core()
            self.discovery_channel.send(['ping', self.hostname, self.uuid])
            self.unlock_core()

    def master_send_nodes_online(self):
        """
        If master, sends the nodes_online over the discovery channel. Registers
        master_ping_nodes() callback after given sleeptimeout in config.
        """
        if self.master:
            nodes_online = []
            for node in list(self.nodes_online.keys()):
                nodes_online.append(self.nodes_online[node])
            self.logger.debug('Publishing online nodes: %s' % nodes_online)

            self.lock_core()
            self.discovery_channel.send(['nodes_online', self.nodes_online, self.uuid])
            self.unlock_core()
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

    # System message methods
    def system_message_add(self, plugin, message, timestamp=time.time()):
        """
        Add a new system message to the file.
        """
        self.logger.info(f"Add system message {plugin}: {message}")
        system_message = self.system_messages_get()
        system_message.append([plugin, message, timestamp])
        try:
            with open(self.system_messages_file, 'w') as f:
                json.dump(system_message, f)
        except IOError as e:
            self.logger.error(f"Could not write to file {e}")

    def system_messages_get(self):
        """
        Return all system messages
        """
        self.logger.debug(f"Get system messages")
        system_message = []
        try:
            if os.path.isfile(self.system_messages_file):
                with open(self.system_messages_file) as f:
                    system_message = json.load(f)
        except IOError as e:
            self.logger.warning("Could not read system messages file (%s)" % e)

        return system_message

    def system_messages_clear(self):
        """
        Clear all system messages
        """
        self.logger.warning(f"Clear system messages")
        try:
            with open(self.system_messages_file, 'w') as f:
                json.dump([["core", "System messages cleared", time.time()]], f)
        except IOError as e:
            self.logger.error("Could not clear system messages (%s)" % e)

    # base methods
    def run(self):
        """
        This method is called right at the beginning of normal operations. (after initialisation)
        Calls start() on all started plugins.
        """
        # Broadcast command list
        for p in self.plugins:
            if p.commands:
                self.lock_core()
                self.discovery_channel.send(['commands', p.commands])
                self.unlock_core()

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
                    # self.logger.debug("process events")
                # cpu utilization from 100% to 0%
                time.sleep(self.main_loop_sleep)
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt detected. Exiting...")
                self.terminate(0)
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
                if not self.terminating:
                    self.logger.critical("Detected hanging core. Exiting...")
                    self.terminate(2)
                else:
                    self.logger.info("Ignoring Timeout exception on core, since shutdown is in progress.")

            # if I hang with threads or subthreads or stuff, comment the following block!
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                file_name = exc_tb.tb_frame.f_code.co_filename
                self.logger.critical(f"Exception in core loop: {e} in {file_name}:{exc_tb.tb_lineno} {exc_type}")
                if self.core_lock.acquire(False):
                    self.logger.warning("Core lock acquired, releasing it for forced shutdown.")
                    self.core_lock.release()
                self.terminate(1)

        self.logger.debug(f"Exiting with return code ({self.return_code})")
        sys.exit(self.return_code)

    def lock_core(self):
        self.core_lock.acquire()

    def unlock_core(self):
        self.core_lock.release()

    def terminate(self, return_code=0):
        """
        Terminate the core. This method will first call the terminate() method on each plugin.
        """

        # Ensure all plugins can check if they should stop to work
        self.lock_core()
        self.terminating = True
        self.unlock_core()

        # setting log level to debug, if not shutting down clean
        if return_code:
            self.logger.setLevel(logging.DEBUG)

        if not self.terminated:
            self.return_code = return_code
            self.logger.warning(f"Core.terminate() called. My {threading.active_count()} threads shall die now.")

            # informing other nodes of my departure
            timeout = 3
            try:
                self.logger.debug(f"Sending byebye to discovery channel (with {timeout} seconds timeout)")
                self.lock_core()
                with Timeout(timeout):
                    self.discovery_channel.send(['byebye', self.hostname, self.uuid])
            except Exception:
                self.logger.debug("Core.terminate() raised an exception on sending byebye")
            finally:
                self.unlock_core()

            # # disconnecting pika
            self.logger.debug("Closing pika connection")
            try:
                with Timeout(timeout):
                    self.connection.close()
            except Exception:
                self.logger.debug("Core.terminate() raised an exception on closing pika connection")

            # gather stats from all plugins
            saveStats = {}
            timeout = 10
            for p in self.plugins:
                self.logger.debug(f"Collecting stats for plugin %s (with {timeout} seconds timeout)" % p.name)
                with Timeout(timeout):
                    saveStats[p.name] = p.save_state(True)
                    self.logger.debug(f"Stats collected for plugin %s" % p.name)

            # save stats to file
            try:
                file = open(self.stats_file, 'w')
                file.write(json.dumps(saveStats))
                file.close()
                self.logger.debug(f"Saved stats to {self.stats_file}")
            except IOError:
                if self.passive:
                    self.logger.info("Could not save stats to file")
                else:
                    self.logger.warning("Could not save stats to file")

            # save presence to file
            try:
                file = open(self.presences_file, 'w')
                file.write(json.dumps(self.presences.dump()))
                file.close()
                self.logger.debug(f"Saving presences to {self.presences_file}")
            except IOError:
                if self.passive:
                    self.logger.info("Could not save presences to file")
                else:
                    self.logger.warning("Could not save presences to file")
            except KeyError:
                # no presence state found for this location
                pass

            # tell plugins to terminate
            timeout = 10
            for p in self.plugins:
                self.logger.debug(f"Calling terminate() on plugin {p.name} (with {timeout} seconds timeout)")
                with Timeout(timeout):
                    p.terminate()
                    self.logger.debug(f"Terminated plugin {p.name}")

            # wait for plugin threads to terminate all its threads in 30 seconds
            timeout = 31
            for p in self.plugins:
                self.logger.debug(f"Calling wait_for_threads() on plugin {p.name} (with {timeout} seconds timeout)")
                with Timeout(timeout):
                    p.wait_for_threads()
                    self.logger.debug(f"All threads ended for plugin {p.name}")

            # check if all child threads are done and kill them if not
            timeout = 5
            self.logger.info(f"Shutdown in progress, {threading.active_count() - 1} child thread(s) still remaining")
            main_thread = threading.current_thread()
            for t in threading.enumerate():
                if t is main_thread:
                    continue
                if t.name in ["MainThread", "ConsoleThread", "Thread-2"]:
                    # Pika connection has a stupid name "Thread-2" and it is not configurable :shrug:
                    self.logger.debug(f"Ignoring thread {t.name} on exit")
                    continue

                self.logger.debug(f'Joining thread {t.name} with PID {t.native_id}')

                try:
                    t.join(timeout)
                    if t.is_alive():
                        self.logger.warning(f"Thread {t.name} with PID {t.native_id} did not exit "
                                            f"after {timeout} seconds.")
                except RuntimeError:
                    self.logger.warning(f"Unable to join thread {t.name} because we would run into a deadlock.")
                    pass

            self.logger.info(f"Shutdown complete. {threading.active_count() - 1} thread(s) remaining")
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
            except queue.Empty:
                break
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                file_name = exc_tb.tb_frame.f_code.co_filename
                self.logger.critical(
                    "Exception 1 in process_timeouts: %s in %s:%s %s" % (e, file_name, exc_tb.tb_lineno, exc_type))

        # Process events
        current_timeout = None
        try:
            now = time.time()
            for timeout in self.timeouts:
                current_timeout = timeout
                if timeout.deadline <= now:
                    self.logger.debug('Processing timeout %s' % timeout.handler)
                    timeout.handler(*timeout.args, **timeout.kwargs)
            self.timeouts = [t for t in self.timeouts if t.deadline > now]
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            file_name = exc_tb.tb_frame.f_code.co_filename
            self.logger.critical(
                "Exception 2 in process_timeouts: %s in %s:%s %s > %s" %
                (e, file_name, exc_tb.tb_lineno, exc_type, current_timeout))
            self.logger.critical('timeout.handler: %s' % current_timeout.handler)
            self.logger.critical('timeout.seconds: %s' % current_timeout.seconds)
            self.logger.critical('timeout.deadline: %s' % current_timeout.deadline)

            # if some event let the client crash, remove it from the list so that the node does not loop forever
            #
            self.timeouts.remove(current_timeout)

            # Handling some really special cases.
            if e == "can't start new thread":
                self.logger.critical("Since we can't start new threads, we should probably restart james")
                self.terminate(1)

    def spawn_subprocess(self, target, on_exit, target_args=None, logger=None):
        """
        Spawns a subprocess with call target and calls on_exit with the return
        when finished
        """
        if not logger:
            logger = self.logger
        logger.debug(f'Spawning subprocess ({target})')

        def run_in_thread(target, on_exit, target_args):
            if target_args is not None:
                self.logger.debug(f'Ending subprocess ({target})')
                self.add_timeout(0, on_exit, target(target_args))
            else:
                self.logger.debug(f'Ending subprocess ({target})')
                self.add_timeout(0, on_exit, target())

        thread = threading.Thread(name=f"{target} {target_args}", target=run_in_thread,
                                  args=(target, on_exit, target_args))
        thread.start()
        self.logger.debug(f"Started thread for {target} with PID {thread.native_id}")
        return thread

    # signal handlers
    def on_kill_sig(self, sig, frame):
        signal.signal(sig, signal.SIG_IGN)  # ignore additional signals
        sig_num = getattr(signal, self.signal_names[sig])
        exit_code = 128 + sig_num
        self.handle_signal(self.signal_names[sig], exit_code)

    def on_fault_sig(self, sig, frame):
        signal.signal(sig, signal.SIG_IGN)  # ignore additional signals
        self.handle_signal(self.signal_names[sig], 1)

    def handle_signal(self, sig_name, exit_code):
        self.logger.warning(f"{sig_name} detected. Exiting with exit code {exit_code}...")
        self.terminate(exit_code)

    # catchall handler
    # def sighandler(self, signal, frame):
    #     self.logger.warning("Uncatched signal %s (%s)" % (self.signal_names[signal], signal))

    #     msg = self.new_message('sighandler')
    #     msg.level = 2
    #     msg.header = "Uncaught SIGNAL detected on %s: %s (%s)" % (self.hostname, self.signal_names[signal], signal)
    #     msg.send()
