
import copy

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
            print("1:%s" % newstatus[self.core.location])
            print("2:%s" % plugin)
            args = []
            args.append(newstatus[self.core.location])
            args.append(plugin)
            print("args: %s" % args)
            self.core.add_timeout(0, self.core.proximity_event, newstatus[self.core.location], plugin)

    def get_all_status(self):
        return self.status

    def get_all_status_copy(self):
        return copy.deepcopy(self.status)

    def get_status_here(self):
        return self.status[self.core.location]