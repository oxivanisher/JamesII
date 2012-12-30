
import sys
import dbus
from dbus.mainloop.glib import DBusGMainLoop

from james.plugin import *

# this plugin is based on http://code.google.com/p/spotify-notify/

class DbusNotifyPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(DbusNotifyPlugin, self).__init__(core, descriptor)

        self.bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
        self.notifyid = 0
        self.commands = False

    def process_message(self, message):
        # Connect to notification interface on DBUS.
        # http://www.galago-project.org/specs/notification/0.9/x408.html#command-notify
        # icon from http://www.iconfinder.com/search/?q=alert
        try:
            self.notifyservice = self.bus.get_object(
                'org.freedesktop.Notifications',
                '/org/freedesktop/Notifications'
            )
            self.notifyservice = dbus.Interface(
                self.notifyservice,
                "org.freedesktop.Notifications"
            )

            if not message.body:
                message.body = ""
            else:
                message.body += "\n\n"

            icon_name = ""
            if int(message.level) == 0:
                icon_name = 'debug.png'
            elif int(message.level) == 1:
                icon_name = 'info.png'
            elif int(message.level) == 2:
                icon_name = 'warn.png'
            elif int(message.level) == 3:
                icon_name = 'error.png'
            try:
                icon_path = os.path.join(os.getcwd(), '../media/', icon_name)
            except Exception:
                icon_path = ''

            brief_msg = ("%s: %s" % (message.sender_host,
                                     message.header))
            long_msg = ("%sPlugin: %s Host: %s" % (message.body,
                                           message.sender_name,
                                           message.sender_host))

            # The second param is the replace id, so get the notify id back,
            # store it, and send it as the replacement on the next call.
            self.notifyid = self.notifyservice.Notify(
                "JamesII Message",
                self.notifyid,
                icon_path,
                brief_msg,
                long_msg,
                [],
                {},
                -1
            )
        except Exception as e:
            pass

descriptor = {
    'name' : 'dbus-notify',
    'help' : 'Dbus notification plugin (desktop only)',
    'command' : 'dbus-notify',
    'mode' : PluginMode.MANUAL,
    'class' : DbusNotifyPlugin
}
