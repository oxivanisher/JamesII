
import jsonrpclib

from james.plugin import *


# http://forum.xbmc.org/showthread.php?tid=111772
# https://github.com/joshmarshall/jsonrpclib/

class XbmcPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(XbmcPlugin, self).__init__(core, descriptor)

        self.show_broadcast = False

        self.commands.create_subcommand('update', 'Initiates a Database update', self.cmd_update)
        self.commands.create_subcommand('test', 'test message', self.cmd_test)
        broadcase_cmd = self.commands.create_subcommand('broadcast', 'Should broadcast messages be sent', None)
        broadcase_cmd.create_subcommand('on', 'Activates broadcast messages', self.cmd_broadcast_on)
        broadcase_cmd.create_subcommand('off', 'Deactivates broadcast messages', self.cmd_broadcast_off)

        user_string = ""
        if self.config['nodes'][self.core.hostname]['username']:
            user_string = self.config['nodes'][self.core.hostname]['username']
        if self.config['nodes'][self.core.hostname]['password']:
            user_string = user_string + ":" + self.config['nodes'][self.core.hostname]['password']
        if user_string:
            user_string = user_string + "@"
        server_string = "%s:%s" % (self.config['nodes'][self.core.hostname]['host'],
                                   self.config['nodes'][self.core.hostname]['port'])
        connection_string = "http://%s%s" % (user_string, server_string)
        self.xbmc_conn = jsonrpclib.Server(connection_string)

        self.updates = 0

    def cmd_update(self, args):
        try:
            self.xbmc_conn.VideoLibrary.Scan()
            self.updates += 1
            self.logger.info("Database updating")
            return ["Video database is updating"]
        except Exception as e:
            return ["Could not send update command %s" % e]

    def cmd_test(self, args):
        try:
            self.xbmc_conn.GUI.ShowNotification("test head", "test body")
            self.logger.info("Test notification sent")
            return ["Notification sent"]
        except Exception as e:
            return ["Could not send notification %s" % e]

    def cmd_broadcast_on(self, args):
        self.show_broadcast = True
        return ["Broadcast messages will be shown"]

    def cmd_broadcast_off(self, args):
        self.show_broadcast = False
        return ["Broadcast messages will no longer be shown"]

    def process_message(self, message):
        if message.level > 0:
            header = 'Level %s Message from %s@%s:' % (message.level,
                                                             message.sender_name,
                                                             message.sender_host)
            body_list = []
            for line in self.utils.list_unicode_cleanup([message.header]):
                body_list.append(line)
            try:
                for line in self.utils.list_unicode_cleanup([message.body]):
                    body_list.append(line)
            except Exception:
                pass
            body = '\n'.join(body_list)
            try:
                self.logger.debug("Showing message: header (%s) body (%s)" % (header, body))
                self.xbmc_conn.GUI.ShowNotification(header, body)
            except Exception as e:
                return ["Could not send notification %s" % e]

    def process_broadcast_command_response(self, args, host, plugin):
        if self.show_broadcast:
            header = "Broadcast from %s@%s" % (plugin, host)
            body = '\n'.join(self.utils.convert_from_unicode(args))
            try:
                self.logger.debug("Showing broadcast message: header (%s) body (%s)" % (header, body))
                self.xbmc_conn.GUI.ShowNotification(header, body)
            except Exception as e:
                return ["Could not send notification %s" % e]

    def return_status(self):
        ret = {}
        ret['updates'] = self.updates
        return ret

descriptor = {
    'name' : 'xbmc',
    'help' : 'Xbmc test module',
    'command' : 'xbmc',
    'mode' : PluginMode.MANAGED,
    'class' : XbmcPlugin,
    'detailsNames' : { 'updates' : "Database updates initated"}
}

