
import uuid
import os
import imp
import sys

class CommandNotFound(Exception):
    pass

class Command(object):

    def __init__(self, name, handler, help="", hide=False):
        self.name = name
        self.handler = handler
        self.help = help
        self.hide = hide


class PluginMode:
    AUTOLOAD = 0
    MANAGED = 1
    MANUAL = 2

class Plugin(object):

    def __init__(self, core, name):
        self.uuid = str(uuid.uuid1())
        self.name = name
        self.core = core
        self.cmds = {}

        self.create_command('help', self.cmd_help, "Show information about plugins commands", True)
        self.create_command('avail', self.cmd_avail, "Show available plugins", True)

    def start(self):
        pass

    def terminate(self):
        pass

    # command methods
    def add_command(self, command):
        self.cmds[command.name] = command

    def create_command(self, name, handler, help="", hide=False):
        self.add_command(Command(name, handler, help, hide))

    def process_command(self, args):
        args = [s.encode('utf-8').strip() for s in args]
        args = filter(lambda s: s != '', args)
        if len(args) < 1:
            return None

        if args[0][0] == '@':
            if args[0][1:] != self.name:
                return None
            args = args[1:]

        if len(args) < 1:
            return None

        try:
            return self.cmds[args[0]].handler(args[1:])
        except KeyError:
            return None

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
            res = self.process_command(body)
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
    def cmd_help(self, args):
        res = []
        for cmd in self.cmds.values():
            if not cmd.hide:
                res.append("%-15s - %s" % (cmd.name, cmd.help))
        return res

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
        if not 'mode' in descriptor.keys():
            raise Exception("Plugin descriptor has no mode field")
        if not 'class' in descriptor.keys():
            raise Exception("Plugin descriptor has no class field")

        cls.descriptors[descriptor['name']] = descriptor

        # Set a name and mode fields in the plugin class
        descriptor['class'].name = descriptor['name']
        descriptor['class'].mode = descriptor['mode']

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
        #sys.stdout.write("Discovering plugins:")
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

