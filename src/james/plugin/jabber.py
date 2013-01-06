
import xmpp
import sys

from james.plugin import *

# http://xmpppy.sourceforge.net/
# FIXME add muc support and send broadcast command responses only there
class JabberThread(PluginThread):

    def __init__(self, plugin, users, cfg_jid, password):
        # FIXME i must become a singleton!
        super(JabberThread, self).__init__(plugin)
        self.cfg_jid = cfg_jid
        self.password = password
        self.active = True
        self.users = users

    def work(self):
        # setup connection
        jid = xmpp.protocol.JID(self.cfg_jid)
        server = jid.getDomain()
        conn = xmpp.Client(server,debug=[])
        conres = conn.connect()

        if not conres:
            print "Unable to connect to server %s!"%server
            self.active = False
        if conres != 'tls':
            print "Warning: unable to estabilish secure connection - TLS failed!"

        authres = conn.auth(jid.getNode(), self.password)
        if not authres:
            print "Unable to authorize on %s - check login/password."%server
            self.active = False
        if authres != 'sasl':
            print "Warning: unable to perform SASL auth on %s. Old authentication method used!"%server

        # registering handlers
        conn.RegisterHandler('message',self.message_callback)

        # lets go online
        conn.sendInitPresence()

        # dive into the endless loops
        self.GoOn(conn)

    def StepOn(self, conn):
        conn.Process(1)

        self.plugin.worker_lock.acquire()

        # see if i must shut myself down
        if self.plugin.worker_exit:
            self.active = False
        # see if we must send messages
        for (header, body, to_jid) in self.plugin.waiting_messages:
            try:
                message = False
                if to_jid:
                    # message to one user
                    message = self.create_message(to_jid, header, body)
                    conn.send(message)
                else:
                    # broadcast message to every user
                    for (jid, name) in self.users:
                        message = self.create_message(jid, header, body)
                        conn.send(message)
            except Exception as e:
                print("Jabber worker ERROR: %s" % e)

        self.plugin.waiting_messages = []
        self.plugin.worker_lock.release()

        if not self.active:
            return 0
        else:
            return 1

    def create_message(self, to, header = [], body = []):
        if len(header) == 0:
            return False
        message_list = filter(lambda s: s != '', header)
        if len(body) > 0:
            message_list = message_list + filter(lambda s: s != '', body)
        message_text = '\n'.join(message_list)
        message = xmpp.protocol.Message(to, message_text)
        message.setAttr('type', 'chat')
        return message

    def GoOn(self, conn):
        while self.StepOn(conn): pass

    # callback handlers
    def message_callback(self, conn, message):
        self.plugin.core.add_timeout(0, self.plugin.process_jabber_message, message)

    # called when the worker ends
    def on_exit(self, result):
        self.plugin.on_worker_exit()

class JabberPlugin(Plugin):

    def __init__(self, core, descriptor):

        super(JabberPlugin, self).__init__(core, descriptor)

        self.rasp_thread = False
        self.worker_exit = False
        self.worker_lock = threading.Lock()
        self.waiting_messages = []
        self.users = []
        # FIXME please implement me as status of jabber james
        self.nodes_online_string = ''

        self.commands.create_subcommand('test', 'Sends a test message over jabber', self.cmd_xmpp_test)
        self.commands.create_subcommand('list', 'Lists all allowed Jabber users', self.cmd_list_users)

    # plugin methods
    def start(self):
        for person in self.core.config['persons'].keys():
            try:
                self.users.append((self.core.config['persons'][person]['jid'], person))
            except Exception:
                pass
        self.start_worker()
    
    def terminate(self):
        self.worker_must_exit()

    # james command methods
    def cmd_xmpp_test(self, args):
        self.send_xmpp_message(["test head"], ["test body line 1", "test body line"])
        return "Sending test message"

    def cmd_list_users(self, args):
        ret = []
        for (jid, name) in self.users:
            ret.append("%-15s %s" % (jid, name))
        return ret

    # methods for worker process
    def send_xmpp_message(self, message_head = [], message_body = [], to = None):
        self.worker_lock.acquire()
        self.waiting_messages.append((message_head, message_body, to))
        self.worker_lock.release()

    def process_jabber_message(self, message):
        jid_data = str(message.getFrom()).split('/')
        jid_from = jid_data[0]
        jid_ress = jid_data[1]

        command = self.core.utils.convert_from_unicode(message.getBody().split())
        if command[0] == 'help':
            search_for = self.core.utils.convert_from_unicode(message.getBody().split())
            help_text = self.jabber_cmd_help(command[1:])
            self.send_xmpp_message(['Commands are:'], help_text, jid_from)
        else:
            self.send_command(command)
        pass

    # worker process help functions
    def jabber_cmd_help(self, args):
        ret = []
        if len(args) > 0:    
            command = self.core.ghost_commands.get_best_match(args)
            if command:
                ret.append("%s:" % (command.help))
                ret.append("%-20s %s" % ('Command:', 'Description:'))
                for line in self.return_command_help_lines(command):
                    ret.append(line)
            else:
                ret.append("Command not found")
        else:
            ret.append("%-20s %s" % ('Command:', 'Description:'))
            for line in self.return_command_help_lines(self.core.ghost_commands, 1):
                ret.append(line)
        return ret

    def return_command_help_lines(self, command_obj, depth = 0):
        ret = []
        for command in sorted(command_obj.subcommands.keys()):
            c = command_obj.subcommands[command]
            if not c.hide:
                ret.append("|%-19s %s" % (depth * "-" + " " + c.name, c.help))
            if len(c.subcommands.keys()) > 0:
                for line in self.return_command_help_lines(c, depth + 1):
                    ret.append(line)
        return ret

    def on_worker_exit(self):
        self.send_broadcast(['XMPP worker exited'])

    # worker control methods
    def start_worker(self):
        # FIXME make me singleton!
        self.worker_lock.acquire()
        self.worker_exit = False
        self.worker_lock.release()
        self.rasp_thread = JabberThread(self,
                                        self.users,
                                        self.core.config['jabber']['jid'],
                                        self.core.config['jabber']['password'])
        self.rasp_thread.start()
        return self.send_broadcast(['XMPP worker starting'])

    def worker_must_exit(self):
        self.worker_lock.acquire()
        self.worker_exit = True
        self.worker_lock.release()
        return self.send_broadcast(['XMPP worker exiting'])

    # plugin event methods
    def process_command_response(self, args, host, plugin):
        message = ['Direct:']
        for line in args:
            message.append("%10s@%-10s: %s" % (plugin, host, line))
        self.send_xmpp_message(message)

    def process_broadcast_command_response(self, args, host, plugin):
        message = ['Broadcast:']
        for line in args:
            message.append("%10s@%-10s: %s" % (plugin, host, line))
        self.send_xmpp_message(message)

    def process_message(self, message):
        if message.level > 1:
            message_text = ['Message with level %s from %s@%s:' % (message.level,
                                                                   message.sender_name,
                                                                   message.sender_host)]
            for line in self.core.utils.list_unicode_cleanup([message.header]):
                message_text.append(line)
            try:
                for line in self.core.utils.list_unicode_cleanup([message.body]):
                    message_text.append(line)
            except Exception:
                pass
            self.send_xmpp_message(message_text)

    def process_proximity_event(self, newstatus):
        if self.core.config['core']['debug']:
            print("Jabber Processing proximity event")
        if not newstatus['status'][self.core.location]:
            self.send_xmpp_message(['Nobody at home. Security measures activated.'])

descriptor = {
    'name' : 'jabber',
    'help' : 'Interface to Jabber (XMPP))',
    'command' : 'jab',
    'mode' : PluginMode.MANAGED,
    'class' : JabberPlugin
}