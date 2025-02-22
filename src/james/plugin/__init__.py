import uuid
import os
import importlib.util
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
        self.commands = core.commands.create_subcommand(descriptor['command'], descriptor['help_text'], None)
        self.data_commands = core.data_commands.create_subcommand(descriptor['command'], descriptor['help_text'], None)
        self.commands.create_subcommand('avail', "Show available plugins", self.cmd_avail, True)
        self.commands.create_subcommand('status', "Shows detailed plugin status", self.cmd_show_plugin_status, True)
        self.commands.create_subcommand('alert', "Alert some text (head) (body)", self.alert, True)

        debug_command = self.commands.create_subcommand('debug', 'Activates or deactivates debug output', None, True)
        debug_command.create_subcommand('on', 'Activate debug', self.cmd_activate_debug)
        debug_command.create_subcommand('off', 'Deactivate debug', self.cmd_deactivate_debug)

        self.data_commands.create_subcommand('status', 'Returns status infos', self.return_status)

        self.config = {}
        self.reload_config()

        self.logger = self.utils.get_logger(self.name, self.core.logger)
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

    def reload_config(self):
        try:
            self.config = self.core.config[self.name]
        except KeyError:
            self.config = {}
            pass

    def start(self):
        pass

    def terminate(self):
        pass

    def save_state(self, verbose=False):
        return self.return_status(verbose)

    def load_state(self, name, default_value):
        try:
            # return self.core.loadedState[self.name][name]
            setattr(self, name, self.core.loadedState[self.name][name])
        except Exception:
            # return default_value
            setattr(self, name, default_value)

    def process_command_response(self, args, host, plugin):
        pass

    def process_data_response(self, my_uuid, name, body, host, plugin):
        pass

    def process_broadcast_command_response(self, args, host, plugin):
        pass

    def send_command(self, args, src_uuid=None):
        """ Sends a command to the queue. Splits it into multiple commands with && as splitter. """
        if not src_uuid:
            src_uuid = self.uuid

        tmpArgsStr = ' '.join(args)
        for tmpCommandStr in tmpArgsStr.split('&&'):
            self.send_request(src_uuid, 'cmd', tmpCommandStr.split())

    def send_request(self, my_uuid, name, body):
        self.core.send_request(my_uuid, name, body, self.core.hostname, self.name)

    def send_response(self, my_uuid, name, body):
        self.core.send_response(my_uuid, name, body, self.core.hostname, self.name)

    def handle_request(self, my_uuid, name, body, host, plugin):
        run_command = True
        if body[0][0] == '@':
            run_command = False
            hosts = body[0].replace('@', '').split(',')
            if self.core.hostname.lower() in [x.lower() for x in hosts]:
                body = body[1:]
                run_command = True

        if run_command:
            if name == 'cmd':
                args = self.utils.list_unicode_cleanup(body)

                try:
                    if self.command == args[0]:
                        self.logger.info('Processing command request (%s)' % ' '.join(args))
                        res = self.core.commands.process_args(args)
                        if res:
                            self.send_response(my_uuid, name, res)
                except KeyError:
                    pass

    def handle_response(self, my_uuid, name, body, host, plugin):
        args = body
        if name == 'cmd' and my_uuid == self.uuid:
            if not isinstance(args, list):
                args = [args]
            self.process_command_response(args, host, plugin)
        elif name == 'broadcast':
            if not isinstance(args, list):
                args = [args]
            self.process_broadcast_command_response(args, host, plugin)

    def send_data_request(self, name, args=[]):
        """ Sends a data command to the queue. """
        self.core.send_data_request(self.core.uuid, name, args, self.core.hostname, self.name)

    def send_data_response(self, my_uuid, name, body):
        """ Sends a data command to the queue. """
        self.core.send_data_response(my_uuid, name, body, self.core.hostname, self.name)

    def handle_data_request(self, my_uuid, name, body, host, plugin):
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
            run_command = True
            if body[0][0] == '@':
                run_command = False
                hosts = body[0].replace('@', '').split(',')
                if self.core.hostname.lower() in [x.lower() for x in hosts]:
                    body = body[1:]
                    run_command = True

            if run_command:
                args = self.utils.list_unicode_cleanup(body)

                try:
                    if self.command == args[0]:
                        self.logger.info('Processing data command request (%s)' % ' '.join(args))
                        res = self.core.data_commands.process_args(args)
                        if res:
                            self.send_data_response(my_uuid, name, res)
                except KeyError:
                    pass

        pass

    def handle_data_response(self, my_uuid, name, body, host, plugin):
        if name == 'status':
            self.process_data_response(my_uuid, name, body, host, plugin)

    def cmd_avail(self, args):
        return self.core.hostname + ' ' + self.name

    def cmd_activate_debug(self, args):
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug('Activating debug')

    def cmd_deactivate_debug(self, args):
        self.logger.debug('Deactivating debug')
        self.logger.setLevel(logging.INFO)

    def wait_for_threads(self, thread_list):
        for thread in thread_list:
            if thread.is_alive():
                self.logger.info("Waiting 10 seconds for thread %s of %s to exit" % (thread.name, self.name))
                thread.join(10.0)

        self.logger.info("All threads of %s ended" % self.name)

    # msg methods
    def process_message(self, message):
        pass

    # presence event method
    def process_presence_event(self, presence_before, presence_now):
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

    # send broadcast msg
    def send_broadcast(self, message):
        self.core.add_timeout(0, self.send_response, self.uuid, 'broadcast', message)

    # return plugin data
    def return_status(self, verbose=False):
        return {}

    def cmd_show_plugin_status(self, args):
        ret = []
        data = self.return_status()
        try:
            for key in list(self.return_status().keys()):
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
        self.name = "Plugin: %s > Class: %s" % (self.plugin.name, self.__class__.__name__)
        self.config = self.plugin.config
        self.utils = self.plugin.utils
        self.logger = self.utils.get_logger('thread.%s' % int(time.time() * 100), self.plugin.logger)
        try:
            if self.config['debug']:
                self.logger.setLevel(logging.DEBUG)
                self.logger.debug("Debug activated")
        except AttributeError:
            pass
        except KeyError:
            pass
        self.logger.debug('Plugin thread initialized for %s' % self.plugin)

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
        Called when thread finished working (synchronized to core)
        """
        pass


class PluginNotAvailable(Exception):
    pass


class Factory(object):
    descriptors = {}

    @classmethod
    def register_plugin(cls, descriptor):
        if 'name' not in list(descriptor.keys()):
            raise Exception("Plugin descriptor has no name field")
        if 'help_text' not in list(descriptor.keys()):
            raise Exception("Plugin descriptor of %s has no help_text field" % descriptor['name'])
        if 'command' not in list(descriptor.keys()):
            raise Exception("Plugin descriptor of %s has no command field" % descriptor['name'])
        if 'mode' not in list(descriptor.keys()):
            raise Exception("Plugin descriptor of %s has no mode field" % descriptor['name'])
        if 'class' not in list(descriptor.keys()):
            raise Exception("Plugin descriptor of %s has no class field" % descriptor['name'])
        if 'detailsNames' not in list(descriptor.keys()):
            raise Exception("Plugin descriptor of %s has no detailsNames field" % descriptor['name'])

        cls.descriptors[descriptor['name']] = descriptor

        descriptor['class'].name = descriptor['name']
        descriptor['class'].descriptor = descriptor

    @classmethod
    def get_plugin_class(cls, name):
        try:
            return cls.descriptors[name]['class']
        except KeyError as e:
            raise PluginNotAvailable("Plugin '%s' not available" % name)

    @classmethod
    def enum_plugin_classes_with_mode(cls, mode):
        for name, descriptor in cls.descriptors.items():
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

            # Load plugin using importlib
            plugin = None
            try:
                # Construct the full path to the module file
                module_path = os.path.join(path, f)
                # Create the spec
                spec = importlib.util.spec_from_file_location(name, module_path)
                if spec is None:
                    plugin_warning.append((name, ImportError("Could not create module spec")))
                    continue

                # Create the module and execute it
                plugin = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(plugin)
                    available_plugins.append(name)
                except Exception as e:
                    plugin_warning.append((name, e))
                    continue

            except ImportError as e:
                plugin_warning.append((name, e))
                continue

            # Check plugin descriptor
            try:
                descriptor = plugin.__dict__['descriptor']
                cls.register_plugin(descriptor)
            except KeyError as e:
                plugin_descr_error.append(name)
                continue

        return available_plugins, plugin_warning, plugin_descr_error
