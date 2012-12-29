
import atexit
import os
import time

from james.plugin import *

class MotionPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(MotionPlugin, self).__init__(core, descriptor)

        self.motion_daemon = '/etc/init.d/motion'
        self.log_file = os.path.join(os.path.expanduser("~"), ".james_motion_log")
        self.log_max_entries = 100
        self.log = []

        self.commands.create_subcommand('img', ('Will be called when motion has a new image file (file)'), self.cmd_img, True)
        self.commands.create_subcommand('log', ('Shows the last ' + self.log_max_entries + ' events'), self.cmd_show_log)
        self.commands.create_subcommand('mov', ('Will be called when motion has a new video file (file)'), self.cmd_mov, True)
        if self.core.os_username == 'root' and os.path.isfile(self.motion_daemon):
	        self.commands.create_subcommand('on', ('Activates the motion daemon'), self.cmd_on)
	        self.commands.create_subcommand('off', ('Deactivates the motion daemon'), self.cmd_off)
		
		atexit.register(self.save_log)

    def load_saved_state(self):
        try:
            file = open(self.log_file, 'r')
            self.log = self.core.utils.convert_from_unicode(json.loads(file.read()))
            file.close()
            if self.core.config['core']['debug']:
                print("Loading motion events from %s" % (self.log_file))
        except IOError:
            pass
        pass

    def save_log(self):
        try:
            file = open(self.log_file, 'w')
            file.write(json.dumps(self.log))
            file.close()
            if self.core.config['core']['debug']:
                print("Saving motion events to %s" % (self.log_file))
        except IOError:
            print("WARNING: Could not save motion events to file!")

    def terminate(self):
        pass

    def log_event(self, timestamp, message, file_name):
        self.log.insert(0, (timestamp, message, file_name))
        while len(self.log) > self.log_max_entries:
            self.log.pop()

    def cmd_showlog(self, args):
        ret = []
        for (timestamp, message, file_name) in self.log:
            ret.append("%-20s %s" % (timestamp, message))
        return ret

    def cmd_mov(self, args):
    	# if at home, delete file. else, move file to data store
    	pass

    def cmd_img(self, args):
    	# copy file to dropbox dir
    	# send message with image link
    	pass

    def cmd_on(self, args):
    	# /etc/init.d/motion start
    	pass

    def cmd_off(self, args):
    	# /etc/init.d/motion stop
    	pass


descriptor = {
    'name' : 'motion',
    'help' : 'Interface to motion',
    'command' : 'motion',
    'mode' : PluginMode.MANAGED,
    'class' : MotionPlugin
}
