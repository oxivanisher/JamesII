
import pickle

# [12:27:13 AM] simon kallweit: ig wuerd eher help wol mache
# [12:27:17 AM] oxi: kk
# [12:27:20 AM] oxi: das waer ou eifacher ^^
# [12:27:39 AM] simon kallweit: jo und irgendwie logischer
# [12:27:49 AM] oxi: jo
# [12:27:56 AM] oxi: guette plan. maches mou so
# [12:28:03 AM] simon kallweit: aus erschts mueestisch ir Command klass e funktion mache wo e string chasch uebergae und dae giter s'command zruegg fauses existiert
# [12:28:13 AM] oxi: de geits naemlech d plugin base class garnuet aa
# [12:28:22 AM] simon kallweit: aso z.b. find_by_name(self, name)
# [12:28:26 AM] oxi: ah kk
# [12:28:27 AM] simon kallweit: isch natuerlech naer rekursiv
# [12:28:50 AM] simon kallweit: nimmsch s'erschte wort waeg, checksch oeb im subcommand dictionary dae waert fingsch, faus jo rueefsch ufem subcommend mitem raescht vom string uf
# [12:28:51 AM] oxi: muesi de es dict zruegg gaeh?
# [12:29:06 AM] simon kallweit: nei eigentlech nur e referaenz ufs command wo referenziert wird vom name
# [12:29:14 AM] oxi: ah ok
# [12:29:26 AM] oxi: das soet kes ding si
# [12:29:34 AM] oxi: (saegi do so blauoeigig :D)
# [12:29:36 AM] simon kallweit: jo isch raecht aehnlech wi process_args oder wisi heisst
# [12:30:57 AM] oxi: jop

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
            # no args and so no command at all.
            return #False

        try:
            return self.subcommands[args[0]].process_args(args[1:])
        except KeyError:
            # the command does not exist
            pass
            #return False
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
