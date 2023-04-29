import time


class Presence(object):
    def __init__(self, core, location, plugin, host, users, last_update=0.0):
        self.core = core
        self.location = location
        self.plugin = plugin
        self.host = host
        self.last_update = last_update
        if self.last_update == 0.0:
            self.last_update = time.time()
        self.users = users

    def is_timeout_ok(self):
        if self.last_update + self.core.config['core']['presence_timeout'] < time.time():
            return False
        else:
            return True

    def get_present_users_here(self):
        if self.location == self.core.location:
            return self.users
        else:
            return []

    def update(self, users):
        # update the changing things of myself
        self.last_update = time.time()
        self.users = users

    def dump(self):
        return {'location': self.location, 'plugin': self.plugin, 'host': self.host, 'last_update': self.last_update,
                'users': self.users}


class Presences(object):
    def __init__(self, core):
        self.presences = []
        self.core = core

    def check_timeouts(self):
        for presence in self.presences:
            if not presence.is_timeout_ok():
                self.core.logger.debug(
                    "Presence from host %s and plugin %s removed, due to node not sending updates (presence_timeout):" % (
                        presence.host, presence.plugin))
                self.presences.remove(presence)

    def get_present_users_here(self):
        persons_here = []
        self.check_timeouts()
        for presence in self.presences:
            persons_here += presence.get_present_users_here()
        return list(set(persons_here))

    def process_presence_message(self, p_msg):
        # process an incoming presence message. returns true if the persons at this location changed, else false
        presence_before = self.get_present_users_here()
        presence_found = False
        for p in self.presences:
            # check if this is the correct presence
            if p.location == p_msg['location'] and p.plugin == p_msg['plugin'] and p.host == p_msg['host']:
                presence_found = True
                p.update(p_msg['users'])

        if not presence_found:
            # this is a new presence
            self.presences.append(
                Presence(self.core, p_msg['location'], p_msg['plugin'], p_msg['host'], p_msg['users']))

        presence_now = self.get_present_users_here()
        if presence_before != presence_now:
            # since get_present_users_here only returns something if this is our location, this should be working
            # also for messages for other locations
            return True, presence_before, presence_now
        else:
            return False, presence_before, presence_now

    def dump(self):
        # dump all curren presences so that it can be saved in json
        dump_return = []
        for p in self.presences:
            dump_return.append(p.dump())
        return dump_return

    def load(self, data):
        # load presences from file (probably due to node restart) and check to remove presences which are over the
        # timeout if i.e. the node was offline for a long time
        for entry in data:
            self.presences.append(Presence(self.core, entry['location'], entry['plugin'], entry['host'], entry['users'],
                                           entry['last_update']))
        self.check_timeouts()
