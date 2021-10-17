
#import pickle
# import jsons
from . import jamesutils
# from dataclasses import dataclass


class CommandNotFound(Exception):
    pass


# @dataclass
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
        for cmd in list(self.subcommands.values()):
            cmd.parent = self

    def add_subcommand(self, subcommand):
        try:
            return self.subcommands[subcommand.name]
        except KeyError:
            subcommand.parent = self
            self.subcommands[subcommand.name] = subcommand
            return subcommand

    def merge_subcommand(self, subcommand):
        if subcommand.name in self.subcommands:
            for s in list(subcommand.subcommands.values()):
                self.subcommands[subcommand.name].merge_subcommand(s)
        else:
            self.subcommands[subcommand.name] = subcommand

    # creates a new subcommand and returns reference to it
    def create_subcommand(self, name, help, handler, hide=False):
        cmd = Command(name, help, handler, hide)
        return self.add_subcommand(cmd)

    # remove a subcommand so plugins can unregister their default commands
    def remove_subcommand(self, name):
        new_cmds = {}
        for cmd in list(self.subcommands.keys()):
            if name != cmd:
                new_cmds[cmd] = self.subcommands[cmd]
        self.subcommands = new_cmds
        return True

    def process_args(self, args):
        try:
            args = jamesutils.JamesUtils(self).list_unicode_cleanup(args)
        except UnicodeDecodeError:
            pass

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
        args = jamesutils.JamesUtils(self).list_unicode_cleanup(args)

        if len(args) < 1:
            return self

        try:
            return self.subcommands[args[0]].get_best_match(args[1:])
        except KeyError:
            return self

    def get_depth(self):
        # this is the same as oneliner:
        # return self.parent.get_depth() + 1 if self.parent else 0
        if not self.parent:
            return 0
        else:
            return self.parent.get_depth() + 1

    def get_subcommand_names(self):
        ret_keys = []
        for subcommand in list(self.subcommands.keys()):
            if not self.subcommands[subcommand].hide:
                ret_keys.append(subcommand)
        return ret_keys

    def __str__(self):
        return "[Command] %s" % self.name

    # def serialize(self):
    #     # return pickle.dumps(self)
    #     return jsons.dump(self)
    #
    # @classmethod
    # def deserialize(cls, data):
    #     return jsons.load(data)
    #     # return pickle.loads(data)
    #     # return pickle.loads(data.encode())

    def list(self, args=None):
        return_list = []
        for subcommand in list(self.subcommands.keys()):
            return_list.append({
                'name': self.subcommands[subcommand].name,
                'help': self.subcommands[subcommand].help,
                'hide': self.subcommands[subcommand].hide
                })
        return return_list
