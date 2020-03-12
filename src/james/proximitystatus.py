import copy


class ProximityStatus(object):
    def __init__(self, core):
        self.status = {'home': False}
        self.core = core
        self.internal_states = {}

    # def set_status_here(self, value, plugin):
    #     if self.status[self.core.location] != value:
    #         self.core.proximity_event(value, plugin)

    def update_all_status(self, newstatus, proximity_type):
        if not len(newstatus):
            self.core.logger.error("ProximityStatus.update_all_status empty: %s from %s" % (newstatus, proximity_type))

        # calculate state before applying the new information
        state_before = False
        for plugin in self.internal_states.keys():
            if self.internal_states[plugin]:
                state_before = True

        # apply the new state state internally
        self.internal_states[proximity_type] = newstatus[self.core.location]

        # calculate state after applying the new information
        state_after = False
        for plugin in self.internal_states.keys():
            if self.internal_states[plugin]:
                state_after = True

        # apply new state
        self.status = newstatus

        # if required, fire new event
        if state_before != state_after:
            self.core.add_timeout(0, self.core.proximity_event, state_after, proximity_type)

    def get_all_status(self):
        return self.status

    def check_for_change(self, proximity_type):
        newstatus = copy.deepcopy(self.status)

        # If the proximity_type is not known, ensure it exists
        if proximity_type not in self.internal_states.keys():
            self.internal_states[proximity_type] = False

        # Check if any proximity_type is true (somebody is at home)
        ret = False
        for plugin in self.internal_states.keys():
            if self.internal_states[plugin]:
                ret = True

        newstatus[self.core.location] = ret
        return newstatus

    def get_status_here(self):
        if self.core.location in self.status.keys():
            return self.status[self.core.location]
        else:
            self.core.logger.debug("ProximityStatus.get_status_here: Location '%s' not found" % self.core.location)
            return False

    def details(self):
        ret = ["Global states (location: state):"]
        for location in self.status.keys():
            ret.append("%20s: %s" % (location, self.status[location]))
        ret.append("Internal state for location %s (plugin: state):" % self.core.location)
        for proximity_type in self.internal_states.keys():
            ret.append("%20s: %s" % (proximity_type, self.internal_states[proximity_type]))
        return ret
