
import json
import uuid
import urllib
import httplib

from james.plugin import *

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
        self.connection_string = "%s%s" % (user_string, server_string)

        self.updateNode = False
        if self.core.hostname in self.config['updatenodes']:
            self.updateNode = True
        self.updates = 0

    def send_rpc(self, method, params = {}):
        id = str(uuid.uuid1())
        headers = { 'Content-Type': 'application/json' }
        rawData = [{"jsonrpc":"2.0", 'id':id, 'method':method, 'params':params}]

        data = json.dumps(rawData)
        h = httplib.HTTPConnection(self.connection_string)
        h.request('POST', '/jsonrpc', data, headers)
        r = h.getresponse()
        rpcReturn = json.loads(r.read())[0]
        if rpcReturn['result'] == 'OK':
            return True
        else:
            self.logger.debug('Unable to process RPC request: (%s) (%s)' % (rawData, rpcReturn))
            return False

    def send_rpc_message(self, title, message):
        return self.send_rpc("GUI.ShowNotification", {"title":title, "message":message})

    def cmd_broadcast_on(self, args):
        self.show_broadcast = True
        return ["Broadcast messages will be shown"]

    def cmd_broadcast_off(self, args):
        self.show_broadcast = False
        return ["Broadcast messages will no longer be shown"]

    def cmd_update(self, args):
        if self.updateNode:
            if self.send_rpc("VideoLibrary.Scan"):
                self.updates += 1
                self.logger.info("Database updating")
                return ["Video database is updating"]
            else:
                return ["Could not send update command %s" % e]
        else:
            self.logger.debug("Not update database because i am no updateNode")

    def cmd_test(self, args):
        if self.send_rpc_message("test head", "test body"):
            self.logger.info("Test notification sent")
            return ["Notification sent"]
        else:
            return ["Could not send notification %s" % e]

    def alert(self, args):
        data = ' '.join(args).split(";")
        if len(data) > 1:
            self.send_rpc_message(data[0], data[1])
        elif len(data) == 1:
            self.send_rpc_message("JamesII Alert", data[0])

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
            
            if self.send_rpc_message(header, body):
                self.logger.debug("Showing message: header (%s) body (%s)" % (header, body))
            else:
                return ["Could not send notification %s" % e]

    def process_broadcast_command_response(self, args, host, plugin):
        if self.show_broadcast:
            header = "Broadcast from %s@%s" % (plugin, host)
            body = '\n'.join(self.utils.convert_from_unicode(args))
            if self.send_rpc_message(header, body):
                self.logger.debug("Showing broadcast message: header (%s) body (%s)" % (header, body))
            else:
                return ["Could not send notification %s" % e]

    def return_status(self):
        ret = {}
        ret['updates'] = self.updates
        ret['updateNode'] = self.updateNode
        return ret

descriptor = {
    'name' : 'xbmc',
    'help' : 'Xbmc test module',
    'command' : 'xbmc',
    'mode' : PluginMode.MANAGED,
    'class' : XbmcPlugin,
    'detailsNames' : { 'updates' : "Database updates initated",
                       'updateNode' : "DB update node"}
}

