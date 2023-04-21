import copy


class ProximityStatus(object):
    def __init__(self, core):
        self.status = {'home': False}
        self.core = core
        self.internal_states = {}

    # def set_status_here(self, value, plugin):
    #     if self.status[self.core.location] != value:
    #         self.core.proximity_event(value, plugin)

    def update_and_return_status_here(self, new_status, proximity_type):
        if not len(new_status):
            self.core.logger.error("ProximityStatus.update_and_check_status empty: %s from %s" %
                                   (new_status, proximity_type))

        # calculate state before applying the new information
        state_before = False
        for loop_type in list(self.internal_states.keys()):
            if self.internal_states[loop_type]:
                state_before = True

        # apply the new state internally
        self.internal_states[proximity_type] = new_status[self.core.location]

        # calculate state after applying the new information
        state_after = False
        for loop_type in list(self.internal_states.keys()):
            if self.internal_states[loop_type]:
                state_after = True

        # apply new "global" state after the proximity_type state is saved internally
        new_status[self.core.location] = state_after
        self.status = new_status

        # if required, fire new event and return the new state
        if state_before != state_after:
            self.core.add_timeout(0, self.core.proximity_event, state_after, proximity_type)

        # return the new state
        return state_after

    def get_all_status(self):
        return self.status

    def check_for_change(self, proximity_type):
        new_status = copy.deepcopy(self.status)

        # If the proximity_type is not known, ensure it exists
        if proximity_type not in list(self.internal_states.keys()):
            self.internal_states[proximity_type] = False

        # Check if any proximity_type is true (somebody is at home)
        ret = False
        for plugin in list(self.internal_states.keys()):
            if self.internal_states[plugin]:
                ret = True

        new_status[self.core.location] = ret
        return new_status

    def get_status_here(self):
        if self.core.location in list(self.status.keys()):
            return self.status[self.core.location]
        else:
            self.core.logger.debug("ProximityStatus.get_status_here: Location '%s' not found" % self.core.location)
            return False

    def details(self):
        ret = ["Global states (location: state):"]
        for location in list(self.status.keys()):
            ret.append("%20s: %s" % (location, self.status[location]))
        ret.append("Internal state for location %s (plugin: state):" % self.core.location)
        for proximity_type in list(self.internal_states.keys()):
            ret.append("%20s: %s" % (proximity_type, self.internal_states[proximity_type]))
        return ret
