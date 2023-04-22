class Status(object):

    def __init__(self, name):
        self.name = name
        self.listeners = []

    def add_listener(self, handler):
        self.listeners.append(handler)

    def remove_listener(self, handler):
        self.listeners.remove(handler)


class AvatarStatus(Status):

    def __init__(self, name):
        super(ProximityStatus, self).__init__("proximity")
        self.status = {'home': False}


class Person(object):
    def __init__(self, name):
        self.name = name
        self.location = None
        self.email = None
        self.jid = None
        self.devices = []

    def create_person(self, name):
        self.name = name
        return self


class DeviceKind:
    BLUETOOTH = 0
    ETHERNET = 1


class Device(object):
    def __init__(self):
        self.kind = None
        self.address = None
        self.owner = None
        self.location = None
        self.description = None

    def create_device(self):
        return self
