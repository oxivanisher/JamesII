
import pickle

# not me: ig wuerd eher help wol mache
# me: kk
# me: das waer ou eifacher ^^
# not me: jo und irgendwie logischer
# me: jo
# me: guette plan. maches mou so
# not me: aus erschts mueestisch ir Command klass e funktion mache wo e string chasch uebergae und dae giter s'command zruegg fauses existiert
# me: de geits naemlech d plugin base class garnuet aa
# not me: aso z.b. find_by_name(self, name)
# me: ah kk
# not me: isch natuerlech naer rekursiv
# not me: nimmsch s'erschte wort waeg, checksch oeb im subcommand dictionary dae waert fingsch, faus jo rueefsch ufem subcommend mitem raescht vom string uf
# me: muesi de es dict zruegg gaeh?
# not me: nei eigentlech nur e referaenz ufs command wo referenziert wird vom name
# me: ah ok
# me: das soet kes ding si
# me: (saegi do so blauoeigig :D)
# not me: jo isch raecht aehnlech wi process_args oder wisi heisst
# me: jop

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
            return

        try:
            return self.subcommands[args[0]].process_args(args[1:])
        except KeyError:
            pass

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
                })
        return return_list
