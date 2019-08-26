
import uuid
import os
import imp
import sys
import threading
import time
import logging

class CommandNotFound(Exception):
    pass

class PluginMode:
    AUTOLOAD = 0
    MANAGED = 1
    MANUAL = 2

class Plugin(object):

    def __init__(self, core, descriptor):
        self.uuid = str(uuid.uuid1()) 
        self.name = descriptor['name']
        self.core = core
        self.utils = self.core.utils
        self.command = descriptor['command']
        self.commands = core.commands.create_subcommand(descriptor['command'], descriptor['help'], None)
        self.data_commands = core.data_commands.create_subcommand(descriptor['command'], descriptor['help'], None)
        self.commands.create_subcommand('avail', "Show available plugins", self.cmd_avail, True)
        self.commands.create_subcommand('status', "Shows detailed plugin status", self.cmd_show_plugin_status, True)
        self.commands.create_subcommand('alert', "Alert some text (head) (body)", self.alert, True)

        debug_command = self.commands.create_subcommand('debug', 'Activates or deactivates debug output', None, True)
        debug_command.create_subcommand('on', 'Activate debug', self.cmd_activate_debug)
        debug_command.create_subcommand('off', 'Deactivate debug', self.cmd_deactivate_debug)

        self.data_commands.create_subcommand('status', 'Returns status informations', self.return_status)

        try:
            self.config = self.core.config[self.name]
        except KeyError:
            self.config = None
            pass

        self.logger = self.utils.getLogger(self.name, self.core.logger)
        try:
            if self.config['debug']:
                self.cmd_activate_debug([])
        except AttributeError:
            pass
        except KeyError:
            pass
        except TypeError:
            pass

        self.worker_threads = []

    def start(self):
        pass

    def terminate(self):
        pass

    def safe_state(self):
        return self.return_status()

    def load_state(self, name, defaultValue):
        try:
            # return self.core.loadedState[self.name][name]
            setattr(self, name, self.core.loadedState[self.name][name])
        except Exception:
            # return defaultValue
            setattr(self, name, defaultValue)

    def process_command_response(self, args, host, plugin):
        pass

    def process_data_response(self, uuid, name, body, host, plugin):
        pass

    def process_broadcast_command_response(self, args, host, plugin):
        pass

    def send_command(self, args, srcUuid = None):
        """ Sends a command to the queue. Splits it into multiple commands with && as splitter. """
        if not srcUuid:
            srcUuid = self.uuid

        tmpArgsStr = ' '.join(args)
        for tmpCommandStr in tmpArgsStr.split('&&'):
            self.send_request(srcUuid, 'cmd', tmpCommandStr.split())

    def send_request(self, uuid, name, body):
        self.core.send_request(uuid, name, body, self.core.hostname, self.name)

    def send_response(self, uuid, name, body):
        self.core.send_response(uuid, name, body, self.core.hostname, self.name)

    def handle_request(self, uuid, name, body, host, plugin):
        runCommand = True
        if body[0][0] == '@':
            runCommand = False
            hosts = body[0].replace('@', '').split(',')
            if self.core.hostname in hosts:
                body = body[1:]
                runCommand = True

        if runCommand:
            if name == 'cmd':
                args = self.utils.list_unicode_cleanup(body)

                try:
                    if self.command == args[0]:
                        self.logger.info('Processing command request (%s)' % ' '.join(args))
                        res = self.core.commands.process_args(args)
                        if res:
                            self.send_response(uuid, name, res)
                except KeyError:
                    pass

    def handle_response(self, uuid, name, body, host, plugin):
        args = body
        if name == 'cmd' and uuid == self.uuid:
            if not isinstance(args, list):
                args = [args]
            self.process_command_response(args, host, plugin)
        elif name == 'broadcast':
            if not isinstance(args, list):
                args = [args]
            self.process_broadcast_command_response(args, host, plugin)

    def send_data_request(self, name, args = []):
        """ Sends a data command to the queue. """
        self.core.send_data_request(self.core.uuid, name, args, self.core.hostname, self.name)

    def send_data_response(self, uuid, name, body):
        """ Sends a data command to the queue. """
        self.core.send_data_response(uuid, name, body, self.core.hostname, self.name)

    def handle_data_request(self, uuid, name, body, host, plugin):
        if name == 'status':
            args = self.utils.list_unicode_cleanup(body)
            try:
                self.logger.debug('Processing status request from %s@%s' % (plugin, host))
                res = self.return_status()
                if res != {}:
                    self.send_data_response(self.core.uuid, name, res)
                    # self.send_data_response(self.uuid, name, res)
            except KeyError:
                pass

        elif name == 'cmd':
            runCommand = True
            if body[0][0] == '@':
                runCommand = False
                hosts = body[0].replace('@', '').split(',')
                if self.core.hostname in hosts:
                    body = body[1:]
                    runCommand = True

            if runCommand:
                args = self.utils.list_unicode_cleanup(body)

                try:
                    if self.command == args[0]:
                        self.logger.info('Processing data command request (%s)' % ' '.join(args))
                        res = self.core.data_commands.process_args(args)
                        if res:
                            self.send_data_response(uuid, name, res)
                except KeyError:
                    pass

        pass

    def handle_data_response(self, uuid, name, body, host, plugin):
        if name == 'status':
            self.process_data_response(uuid, name, body, host, plugin)

    def cmd_avail(self, args):
        return self.core.hostname + ' ' + self.name

    def cmd_activate_debug(self, args):
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug('Activating debug')

    def cmd_deactivate_debug(self, args):
        self.logger.debug('Deactivating debug')
        self.logger.setLevel(logging.INFO)

    def wait_for_threads(self, threadList):
        for thread in threadList:
            if thread.is_alive():
                self.logger.info("Waiting 3 seconds for thread %s to exit" % thread.name)
                thread.join(3)

        self.logger.info("All threads ended")

    # message methods
    def process_message(self, message):
        pass

    # proximity event method
    def process_proximity_event(self, newstatus):
        pass

    # discovery event method
    def process_discovery_event(self, msg):
        pass

    # command event methods
    def process_command_request_event(self, msg):
        pass

    def process_command_response_event(self, msg):
        pass

    # command event methods
    def process_data_request_event(self, msg):
        pass

    def process_data_response_event(self, msg):
        pass

    # send broadcast message
    def send_broadcast(self, message):
        self.core.add_timeout(0, self.send_response, self.uuid, 'broadcast', message)

    # return plugin data
    def return_status(self):
        return {}

    def cmd_show_plugin_status(self, args):
        ret = []
        data = self.return_status()
        try:
            for key in self.return_status().keys():
                ret.append("%-30s: %s" % (Factory.descriptors[self.name]['detailsNames'][key], data[key]))
            return ret
        except AttributeError:
            self.logger.error("Error on cmd_show_plugin_status in %s" % self.name)

    def alert(self, args):
        pass

class PluginThread(threading.Thread):

    def __init__(self, plugin):
        super(PluginThread, self).__init__()
        self.plugin = plugin
        self.config = self.plugin.config
        self.utils = self.plugin.utils
        self.logger = self.utils.getLogger('thread.%s' % int(time.time() * 100), self.plugin.logger)
        try:
            if self.config['debug']:
                self.logger.setLevel(logging.DEBUG)
                self.logger.debug("Debug activated")
        except AttributeError:
            pass
        except KeyError:
            pass
        self.logger.debug('Thread initialized')

    def work(self):
        """
        Method representing the threads activity
        """
        pass

    def run(self):
        result = self.work()
        self.plugin.core.add_timeout(0, self.on_exit, result)

    def on_exit(self, result):
        self.logger.debug('Thread exited')
        """
        Called when thread finished working (synchroized to core)
        """
        pass

class PluginNotAvailable(Exception):
    pass

class Factory(object):

    descriptors = {}

    @classmethod
    def register_plugin(cls, descriptor):
        if not 'name' in descriptor.keys():
            raise Exception("Plugin descriptor has no name field")
        if not 'help' in descriptor.keys():
            raise Exception("Plugin descriptor of %s has no help field" % descriptor['name'])
        if not 'command' in descriptor.keys():
            raise Exception("Plugin descriptor of %s has no command field" % descriptor['name'])
        if not 'mode' in descriptor.keys():
            raise Exception("Plugin descriptor of %s has no mode field" % descriptor['name'])
        if not 'class' in descriptor.keys():
            raise Exception("Plugin descriptor of %s has no class field" % descriptor['name'])
        if not 'detailsNames' in descriptor.keys():
            raise Exception("Plugin descriptor of %s has no detailsNames field" % descriptor['name'])

        cls.descriptors[descriptor['name']] = descriptor

        descriptor['class'].name = descriptor['name']
        descriptor['class'].descriptor = descriptor

    @classmethod
    def get_plugin_class(cls, name):
        try:
            return cls.descriptors[name]['class']
        except KeyError, e:
            raise PluginNotAvailable("Plugin '%s' not available" % (name))

    @classmethod
    def enum_plugin_classes_with_mode(cls, mode):
        for name, descriptor in cls.descriptors.iteritems():
            if descriptor['mode'] == mode:
                yield descriptor['class']

    @classmethod
    def find_plugins(cls, path):
        files = os.listdir(path)

        available_plugins = []
        plugin_warning = []
        plugin_descr_error = []
        for f in files:
            # Get module filename and extension
            (name, ext) = os.path.splitext(os.path.basename(f))
            # Skip if not valid module
            if ext != '.py' or name == '__init__':
                continue
            # Load plugin
            plugin = None
            info = imp.find_module(name, [path])
            try:
                plugin = imp.load_module(name, *info)
                available_plugins.append(name)
            except ImportError, e:
                plugin_warning.append((name, e))
                continue
            # Check plugin descriptor
            try:
                descriptor = plugin.__dict__['descriptor']
                cls.register_plugin(descriptor)
            except KeyError, e:
                plugin_descr_error.append(name)
                continue

        return (available_plugins, plugin_warning, plugin_descr_error)

