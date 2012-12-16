
import pickle

class CommandNotFound(Exception):
    pass

class Command(object):

    def __init__(self, name, help='', handler=None, hide=False):
        self.parent = None
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

        # repair parent links
        for cmd in self.subcommands.values():
            cmd.parent = self

    def add_subcommand(self, subcommand):
        try:
            return self.subcommands[subcommand.name]
        except KeyError:
            subcommand.parent = self
            self.subcommands[subcommand.name] = subcommand
            return subcommand

    # creates a new subcommand and returns reference to it
    def create_subcommand(self, name, help, handler, hide=False):
        cmd = Command(name, help, handler, hide)
        return self.add_subcommand(cmd)

    def process_args(self, args):
        args = [s.encode('utf-8').strip() for s in args]
        args = filter(lambda s: s != '', args)

        if self.handler:
            return self.handler(args)

        if len(args) < 1:
            return

        try:
            return self.subcommands[args[0]].process_args(args[1:])
        except KeyError:
            return None

    # return best matching command (or self)
    def get_best_match(self, args):
        args = [s.encode('utf-8').strip() for s in args]
        args = filter(lambda s: s != '', args)

        if len(args) < 1:
            return self

        try:
            return self.subcommands[args[0]].get_best_match(args[1:])
        except KeyError:
            return self

    def get_depth(self):
        # return self.parent.get_depth() + 1 if self.parent else 0
        if not self.parent:
            return 0
        else:
            return self.parent.get_depth() + 1

    # FIXME option to discard hidden commands
    def get_subcommand_names(self):
        return self.subcommands.keys()

    # def dump(self, indent = ''):
    #     print indent + self.name
    #     for subcommand in self.subcommands.keys():
    #         self.subcommands[subcommand].dump(indent + '\t')

    def __str__(self):
        return "[Command] %s" % (self.name)

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
                })
        return return_list
