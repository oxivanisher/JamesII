
import atexit
import os
import time
import json

from james.plugin import *

class MotionPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(MotionPlugin, self).__init__(core, descriptor)

        self.motion_daemon = '/etc/init.d/motion'
        self.log_file = os.path.join(os.path.expanduser("~"), ".james_motion_log")
        self.log_max_entries = 100
        self.log = []

        self.commands.create_subcommand('img', ('Will be called when motion has a new image file (file)'), self.cmd_img, True)
        self.commands.create_subcommand('log', ('Shows the last %s events' % self.log_max_entries), self.cmd_show_log)
        self.commands.create_subcommand('mov', ('Will be called when motion has a new video file (file)'), self.cmd_mov, True)
        self.commands.create_subcommand('cam_lost', ('Will be called when motion loses the camera'), self.cmd_cam_lost, True)
        if self.core.os_username == 'root' and os.path.isfile(self.motion_daemon):
	        self.commands.create_subcommand('on', ('Activates the motion daemon'), self.cmd_on)
	        self.commands.create_subcommand('off', ('Deactivates the motion daemon'), self.cmd_off)
		
		atexit.register(self.save_log)

        if self.core.proximity_status.get_status_here():
            self.core.add_timeout(0, self.cam_control, False)
        else:
            self.core.add_timeout(0, self.cam_control, True)

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

    def log_event(self, message, file_name):
        self.log.insert(0, (int(time.time()), message, file_name))
        while len(self.log) > self.log_max_entries:
            self.log.pop()

    def cmd_show_log(self, args):
    	var = 0
    	return var / var
        ret = []
        for (timestamp, message, file_name) in self.log:
            ret.append("%-20s %s" % (self.core.utils.get_short_age(timestamp), message))
        return ret

    def cmd_cam_lost(self, args):
    	print("cam lost")
    	pass

    def cmd_mov(self, args):
    	print("mov")
    	# if at home and not sleep mode ended, delete file.
    	 # if sleep mode was enabled, delete file but send some response or broadcast?

    	#else, move file to data store
    	pass

    def cmd_img(self, args):
    	if self.core.proximity_status.get_status_here():
    		try:
	    		os.remove(args[0])
	    		self.core.send_broadcast('Image file for motion removed')
	    	except Exception as e:
	    		print("Motion was unable to remove image file (%s)" % (args[0]))
    		pass
    	else:
    		self.send_broadcast(['Motion: New image file: %s' % args[0]])
    		self.log_event("Image file created", args[0])
	    	# copy file to dropbox dir
	    	# send message with image link
    	pass

    def cmd_on(self, args):
    	self.core.add_timeout(0, self.cam_control, True)
    	return ["Motion will be started"]

    def cmd_off(self, args):
    	self.core.add_timeout(0, self.cam_control, False)
    	return ["Motion will be stopped"]

    def cam_control(self, switch_on):
    	if switch_on:
    		self.core.utils.popenAndWait(['/etc/init.d/motion', 'start'])
    	else:
    		self.core.utils.popenAndWait(['/etc/init.d/motion', 'stop'])
    	print ("switch: %s" % switch_on)

    # react on proximity events
    def process_proximity_event(self, newstatus):
        if (time.time() - self.core.startup_timestamp) > 10:
            if self.core.config['core']['debug']:
                print("Motion processing proximity event")
            if newstatus['status'][self.core.location]:
                self.cmd_off(None)
            else:
                self.cmd_on(None)
        return True

descriptor = {
    'name' : 'motion',
    'help' : 'Interface to motion',
    'command' : 'motion',
    'mode' : PluginMode.MANAGED,
    'class' : MotionPlugin
}
