
import uuid
import os
import imp
import sys

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
        # self.command = command
        self.commands = core.commands.create_subcommand(descriptor['command'], descriptor['help'], None)

        #FIXME: include me special
        #self.commands.create_subcommand('help', "Show information about plugins commands", self.cmd_help, True)

        self.commands.create_subcommand('avail', "Show available plugins", self.cmd_avail, True)

        # self.create_command('help', self.cmd_help, "Show information about plugins commands", True)
        # self.create_command('avail', self.cmd_avail, "Show available plugins", True)

    def start(self):
        pass

    def terminate(self):
        pass

    def process_command_response(self, args, host, plugin):
        pass

    def send_command(self, args):
        """ Sends a command to the queue. """
        self.send_request(self.uuid, 'cmd', args)

    def send_request(self, uuid, name, body):
        self.core.send_request(uuid, name, body, self.core.hostname, self.name)

    def send_response(self, uuid, name, body):
        self.core.send_response(uuid, name, body, self.core.hostname, self.name)

    def handle_request(self, uuid, name, body, host, plugin):
        if name == 'cmd':
            res = self.core.commands.process_args(body)
            if res:
                self.send_response(uuid, name, res)

    def handle_response(self, uuid, name, body, host, plugin):
        if uuid == self.uuid:
            if name == 'cmd':
                args = body
                if not isinstance(args, list):
                    args = [args]
                self.process_command_response(args, host, plugin)

    # default commands
    # def cmd_help(self, args):
    #     res = []
    #     for cmd in self.commands.list():
    #         print cmd
    #         #if not cmd.hide: #need this
    #         #res.append("%-15s - %s" % (cmd['name'], cmd['help']))
    #         pass
    #     return res

    def cmd_avail(self, args):
        return os.uname()[1] + ' ' + self.name

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
        plugin_load_error = []

        output = "Discovering plugins:"
        for f in files:
            # Get module filename and extension
            (name, ext) = os.path.splitext(os.path.basename(f))
            # Skip if not valid module
            if ext != '.py' or name == '__init__':
                continue
            # Load plugin
            output += (" %s" % (name))
            plugin = None
            info = imp.find_module(name, [path])
            try:
                plugin = imp.load_module(name, *info)
            except ImportError, e:
                plugin_load_error.append("Failed to initialize plugin '%s' (%s)" % (name, e))
                continue
            # Check plugin descriptor
            try:
                descriptor = plugin.__dict__['descriptor']
                cls.register_plugin(descriptor)
            except KeyError, e:
                plugin_load_error.append("Plugin '%s' has no valid descriptor" % (name))
                continue

        print(output)
        # FIXME: wie mache ich hier core.config['core']['debug'] ?
        # -->> logger package

        for e in plugin_load_error:
            print(e)

