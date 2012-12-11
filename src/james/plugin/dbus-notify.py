
import sys
import dbus
from dbus.mainloop.glib import DBusGMainLoop

from james.plugin import *

# this plugin is based on http://code.google.com/p/spotify-notify/

class DbusNotifyPlugin(Plugin):

    def __init__(self, core):
        super(DbusNotifyPlugin, self).__init__(core, DbusNotifyPlugin.name)

        self.bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
        self.notifyid = 0

    def process_message(self, message):
        # Connect to notification interface on DBUS.
        self.notifyservice = self.bus.get_object(
            'org.freedesktop.Notifications',
            '/org/freedesktop/Notifications'
        )
        self.notifyservice = dbus.Interface(
            self.notifyservice,
            "org.freedesktop.Notifications"
        )

        # The second param is the replace id, so get the notify id back,
        # store it, and send it as the replacement on the next call.
        self.notifyid = self.notifyservice.Notify(
            "JamesII Message",
            self.notifyid,
            '',
            ("%s (%s@%s)\n" % (message.header,
                             message.sender_name,
                             message.sender_host)),
            ("%s" % (message.body)),
            [],
            {},
            2
        )

descriptor = {
    'name' : 'dbus-notify',
    'mode' : PluginMode.MANAGED,
    'class' : DbusNotifyPlugin
}
