
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
        self.command = descriptor['command']
        self.commands = core.commands.create_subcommand(descriptor['command'], descriptor['help'], None)
        self.data_commands = core.data_commands.create_subcommand(descriptor['command'], descriptor['help'], None)
        self.commands.create_subcommand('avail', "Show available plugins", self.cmd_avail, True)

        debug_command = self.commands.create_subcommand('debug', 'Activates or deactivates debug output', None, True)
        debug_command.create_subcommand('on', 'Activate debug', self.cmd_activate_debug)
        debug_command.create_subcommand('off', 'Deactivate debug', self.cmd_deactivate_debug)

        self.logger = self.core.utils.getLogger(self.name, self.core.logger)

    def start(self):
        pass

    def terminate(self):
        pass

    def process_command_response(self, args, host, plugin):
        pass

    def process_data_response(self, args, host, plugin):
        pass

    def process_broadcast_command_response(self, args, host, plugin):
        pass

    def send_command(self, args):
        """ Sends a command to the queue. """
        self.send_request(self.uuid, 'cmd', args)

    def send_data_command(self, args):
        """ Sends a data command to the queue. """
        self.send_request(self.uuid, 'data', args)

    def send_request(self, uuid, name, body):
        self.core.send_request(uuid, name, body, self.core.hostname, self.name)

    def send_response(self, uuid, name, body):
        self.core.send_response(uuid, name, body, self.core.hostname, self.name)

    def handle_request(self, uuid, name, body, host, plugin):
        if name == 'cmd':
            args = self.core.utils.list_unicode_cleanup(body)

            try:
                if self.command == args[0]:
                    self.logger.info('Processing command request (%s)' % ' '.join(args))
                    res = self.core.commands.process_args(args)
                    if res:
                        self.send_response(uuid, name, res)
            except KeyError:
                pass
        elif name == 'data':
            args = self.core.utils.list_unicode_cleanup(body)

            try:
                if self.command == args[0]:
                    self.logger.info('Processing data command (%s)' % ' '.join(args))
                    res = self.core.data_commands.process_args(args)
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
        if name == 'data' and uuid == self.uuid:
            self.process_data_response(args, host, plugin)
        elif name == 'broadcast':
            if not isinstance(args, list):
                args = [args]
            self.process_broadcast_command_response(args, host, plugin)

    def cmd_avail(self, args):
        return self.core.hostname + ' ' + self.name

    def cmd_activate_debug(self, args):
        self.logger.info('Activating debug')
        self.logger.setLevel(logging.DEBUG)

    def cmd_deactivate_debug(self, args):
        self.logger.info('Deactivating debug')
        self.logger.setLevel(logging.INFO)

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

    # send broadcast message
    def send_broadcast(self, message):
        self.core.add_timeout(0, self.send_response, self.uuid, 'broadcast', message)

class PluginThread(threading.Thread):

    def __init__(self, plugin):
        super(PluginThread, self).__init__()
        self.plugin = plugin
        self.logger = self.plugin.core.utils.getLogger('thread.%s' % int(time.time() * 100), self.plugin.logger)
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
            raise Exception("Plugin descriptor has no help field")
        if not 'command' in descriptor.keys():
            raise Exception("Plugin descriptor has no command field")
        if not 'mode' in descriptor.keys():
            raise Exception("Plugin descriptor has no mode field")
        if not 'class' in descriptor.keys():
            raise Exception("Plugin descriptor has no class field")

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

