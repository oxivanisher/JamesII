import json
import pickle
import copy

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

class Command(object):

    def __init__(self, name, help='', handler=None, hide=False):
        self.name = name
        self.help = help
        self.handler = handler
        self.hide = hide
        self.subcommands = {}

    def __getstate__(self):
        result = self.__dict__.copy()
        del result['handler']
        return result

    def __setstate__(self, dict):
        self.__dict__ = dict
        self.handler = None

    def add_subcommand(self, subcommand):
        try:
            return self.subcommands[subcommand.name]
        except KeyError:
            self.subcommands[subcommand.name] = subcommand
            return subcommand

    # creates a new subcommand and returns reference to it
    def create_subcommand(self, name, help, handler, hide=False):
        cmd = Command(name, help, handler, hide)
        return self.add_subcommand(cmd)

    def process_args(self, args):
        # print('execute cmd ', self.name)

        if self.handler:
            return self.handler(args)

        args = [s.encode('utf-8').strip() for s in args]
        args = filter(lambda s: s != '', args)
        if len(args) < 1:
            return False

        try:
            return self.subcommands[args[0]].process_args(args[1:])
        except KeyError:
            #pass
            return False
            #was pass

    # def dump(self, indent = ''):
    #     print indent + self.name
    #     for subcommand in self.subcommands.keys():
    #         self.subcommands[subcommand].dump(indent + '\t')

    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, data):
        return pickle.loads(data)

    def list(self, args=None):
        return_list = []
        for subcommand in self.subcommands.keys():
            return_list.append({
                'name' : self.subcommands[subcommand].name,
                'help' : self.subcommands[subcommand].help,
                'hide' : self.subcommands[subcommand].hide
                #Need hide here for cmd_help in james/plugin/__init !
                })
        return return_list

    def show_help(self, args):
        try:
            return self.subcommands[args[0]].show_help(args[1:])
        except Exception as e:
            return self.help
