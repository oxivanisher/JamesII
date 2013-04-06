
import atexit
import os
import time
import json
import shutil
import ntpath

from james.plugin import *

class MotionPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(MotionPlugin, self).__init__(core, descriptor)

        # FIXME (motion) copy files to folders for left events and bring order to the motion chaos :)

        self.motion_daemon = '/etc/init.d/motion'
        self.log_file = os.path.join(os.path.expanduser("~"), ".james_motion_log")
        self.log_max_entries = 100
        self.log = []
        self.watch_mode = False

        self.commands.create_subcommand('img', ('Will be called when motion has a new image file (file)'), self.cmd_img, True)
        self.commands.create_subcommand('mov', ('Will be called when motion has a new video file (file)'), self.cmd_mov, True)
        self.commands.create_subcommand('cam_lost', ('Will be called when motion loses the camera'), self.cmd_cam_lost, True)
        self.commands.create_subcommand('log', ('Shows the last %s events' % self.log_max_entries), self.cmd_show_log)
        self.commands.create_subcommand('watch', ('Motion watches over you and starts the radio when movement is detected'), self.cmd_watch_on)
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
            # self.log = self.core.utils.convert_from_unicode(json.loads(file.read()))
            self.log = json.loads(file.read())
            file.close()
            self.logger.debug("Loading motion events from %s" % (self.log_file))
        except IOError:
            pass
        pass

    def save_log(self):
        try:
            file = open(self.log_file, 'w')
            file.write(json.dumps(self.log))
            file.close()
            self.logger.debug("Saving motion events to %s" % (self.log_file))
        except IOError:
            self.logger.warning("Could not save motion events to file!")

    def terminate(self):
        pass

    def log_event(self, message, file_name):
        self.log.insert(0, (int(time.time()), message, file_name))
        while len(self.log) > self.log_max_entries:
            self.log.pop(0)
        return True

    def cmd_watch_on(self, args):
        if self.core.proximity_status.get_status_here():
            self.watch_mode = True
            self.cam_control(True)
        else:
            self.logger.debug('MPD Wakeup not activated. You are not here.')
            return (["MPD Wakeup not activated. You are not here."])

    def cmd_show_log(self, args):
        var = 0
        return var / var
        ret = []
        for (timestamp, message, file_name) in self.log:
            ret.append("%-20s %s" % (self.core.utils.get_short_age(timestamp), message))
        return ret

    def cmd_cam_lost(self, args):
        message = self.core.new_message(self.name)
        message.level = 3
        message.header = ("Cam disconnected!")
        message.send()
        # deactivate motion
        self.cam_control(False)

    def cmd_mov(self, args):
        if self.core.proximity_status.get_status_here():
            # somebody is at home. delete the file and deactivate motion
            try:
                if self.watch_mode:
                    self.logger.info('Motion Watching starts mpd radio on')
                    self.send_command(['mpd', 'radio', 'on'])
                self.watch_mode = False
                os.remove(args[0])
                self.logger.info('Motion video file removed')
                self.cam_control(False)
            except Exception as e:
                self.logger.error("Motion video file error: %s" % e)
        else:
            # nobody is at home .. so ...why do we have movement? DANGER WILL ROBINSON!
            try:
                file_path = args[0]
            except Exception as e:
                return (["Please add the path to the file (%s)" % (e)])

            file_name = ntpath.basename(file_path)
            if self.move_file(file_path, self.core.config['motion']['target-dir']):
                self.logger.info('Motion: New Video file %s' % file_name)

    def cmd_img(self, args):
        if self.core.proximity_status.get_status_here():
            # somebody is at home. delete the file and do nothing else
            try:
                os.remove(args[0])
                self.logger.info('Motion image file removed')
            except Exception as e:
                pass
        else:
            # nobody is at home .. so ...why do we have movement? DANGER WILL ROBINSON!
            try:
                file_path = args[0]
            except Exception as e:
                return (["Please add the path to the file (%s)" % (e)])

            file_name = ntpath.basename(file_path)
            self.logger.info('Motion: New image file %s' % file_name)

            message = self.core.new_message(self.name)
            message.level = 2
            message.header = ("Movement detected at %s" % (self.core.location))

            if self.move_file(file_path, self.core.config['motion']['dropbox-dir']):
                message.body = ("%s/%s" % (self.core.config['motion']['dropbox-url'], file_name))
            message.send()

            if self.move_file(file_path, self.core.config['motion']['target-dir']):
                self.logger.info('Motion: New Image file %s' % file_name)

    def move_file(self, src_file, dst_path):
        try:
            file_name = ntpath.basename(src_file)
            shutil.copy(src_file, os.path.join(dst_path, file_name))
            return True
        except Exception:
            return False

    def cmd_on(self, args):
        self.core.add_timeout(0, self.cam_control, True)
        return ["Motion will be started"]

    def cmd_off(self, args):
        self.core.add_timeout(0, self.cam_control, False)
        return ["Motion will be stopped"]

    def cam_control(self, switch_on):
        if switch_on:
            self.logger.info('Motion is starting')

            self.core.spawnSubprocess(self.cam_on,
                                      self.on_cam_controll_callback,
                                      None,
                                      self.logger)

        else:
            self.logger.info('Motion is stopping')
            self.watch_mode = False

            self.core.spawnSubprocess(self.cam_off,
                                      self.on_cam_controll_callback,
                                      None,
                                      self.logger)

    def cam_on(self):
        self.core.utils.popenAndWait(['/etc/init.d/motion', 'start'])
        return "Motion started"

    def cam_off(self):
        self.core.utils.popenAndWait(['/etc/init.d/motion', 'stop'])
        return "Motion stopped"

    def on_cam_controll_callback(self, state):
        self.logger.info(state)

    # react on proximity events
    def process_proximity_event(self, newstatus):
        self.logger.debug("Motion processing proximity event")
        if newstatus['status'][self.core.location]:
            self.watch_mode = False
            self.cmd_off(None)
        else:
            self.watch_mode = False
            self.cmd_on(None)
        return True

descriptor = {
    'name' : 'motion',
    'help' : 'Interface to motion',
    'command' : 'motion',
    'mode' : PluginMode.MANAGED,
    'class' : MotionPlugin
}
