
import xmpp
import sys
import time

from james.plugin import *

# http://xmpppy.sourceforge.net/
# http://stackoverflow.com/questions/3528373/how-to-create-muc-and-send-messages-to-existing-muc-using-python-and-xmpp
# http://xmpppy-guide.berlios.de/html/
# http://stackoverflow.com/questions/2381597/xmpp-chat-accessing-contacts-status-messages-with-xmpppys-roster

# http://comments.gmane.org/gmane.network.jabber.lib.xmpppy/663
# http://nullege.com/codes/search/xmpp.Client.reconnectAndReauth
# http://xmpp.org/extensions/xep-0045.html/#disco-occupant

class JabberThread(PluginThread):

    def __init__(self, plugin, users, cfg_jid, password, muc_room = None, muc_nick = 'james'):
        # FIXME i must become a singleton!
        super(JabberThread, self).__init__(plugin)
        self.cfg_jid = cfg_jid
        self.password = password
        self.active = True
        self.users = users
        self.status_message = ''
        self.muc_room = muc_room
        self.muc_nick = muc_nick
        self.conn = False
        self.roster = {}
        self.muc_users = {}

    # jabber connection methods
    def xmpp_connect(self):
        # setup connection
        jid = xmpp.protocol.JID(self.cfg_jid)
        self.conn = xmpp.Client(jid.getDomain(),debug=[])
        conres = self.conn.connect()

        if not conres:
            self.logger.error("Unable to connect to server %s!" % jid.getDomain())
            self.active = False
        else:
            self.active = True
    
        if self.active:
            if conres != 'tls':
                self.logger.warning("Unable to estabilish secure connection - TLS failed!")

            authres = self.conn.auth(jid.getNode(), self.password)

            if not authres:
                self.logger.error("Unable to authorize on %s - check login/password." % jid.getDomain())
                self.active = False
            if authres != 'sasl':
                self.logger.warning("Warning: unable to perform SASL auth on %s. Old authentication method used!" % server)

            # lets go online
            self.conn.sendInitPresence(requestRoster=0)

            # registering handlers
            self.conn.RegisterHandler('message', self.message_callback)
            self.conn.RegisterHandler('presence', self.presence_callback)
            self.conn.RegisterHandler('disconnect', self.disconnect_callback)
            self.conn.RegisterHandler('iq', self.iq_callback)

            # do we have to connect to a muc room?
            if self.muc_room:
                self.conn.send(xmpp.Presence(to='%s/%s' % (self.muc_room, self.muc_nick)))

            # get our roster
            my_roster = self.conn.getRoster()
            for i in my_roster.getItems():
                self.roster[i] = my_roster.getStatus(i)
            self.roster = self.plugin.core.utils.convert_from_unicode(self.roster)

            # self.logger.debug("Jabber worker roster: %s" % self.roster)
            return True

        else:
            # unable to connect to server
            self.xmpp_disconnect()
            return False

    def xmpp_disconnect(self):
        self.plugin.worker_lock.acquire()
        exit = self.plugin.worker_exit
        self.plugin.worker_lock.release()
        if not exit:
            try:
                while not self.conn.reconnectAndReauth():
                    self.logger.debug("Reconnecting...")
                    time.sleep(5)
            except:
                self.conn = False
                self.xmpp_connect()
        else:
            self.active = False

    # base worker methods
    def work(self):
        if self.xmpp_connect():
            # dive into the endless loops
            self.GoOn()
        else:
            self.plugin.worker_lock.acquire()
            exit = self.plugin.worker_exit
            self.plugin.worker_lock.release()
            if not exit:
                time.sleep(2)
                self.work()
            else:
                self.active = False

    def StepOn(self):
        try:
            self.conn.Process(1)
        except IOError:
            self.xmpp_disconnect()
            sys.exc_clear()
        except:
            pass
        if not self.conn.isConnected(): self.xmpp_disconnect()

        self.plugin.worker_lock.acquire()

        # see if i must shut myself down
        if self.plugin.worker_exit:
            self.active = False
        # see if we must send direct messages
        for (header, body, to_jid) in self.plugin.waiting_messages:
            try:
                message = False
                if to_jid:
                    # message to one user
                    message = self.create_message(to_jid, header, body)
                    self.conn.send(message)
                else:
                    # broadcast message to every user
                    for (jid, name) in self.users:
                        message = self.create_message(jid, header, body)
                        self.conn.send(message)
            except Exception as e:
                self.logger.debug("Send direct msg ERROR: %s" % e)
        # see if we must send muc messages
        if self.muc_room:
            for (header, body) in self.plugin.waiting_muc_messages:
                try:
                    msg_text = '\n'.join(header)
                    if len(body):
                        msg_text = msg_text + '\n' + '\n'.join(body)
                    msg = xmpp.protocol.Message(body=msg_text)
                    msg.setTo(self.muc_room)
                    msg.setType('groupchat')
                    self.conn.send(msg)
                except Exception as e:
                    self.logger.debug("Send muc msg ERROR: %s" % e)
        # see if we must change our status
        if self.plugin.jabber_status_string != self.status_message:
            self.status_message = self.plugin.jabber_status_string
            new_status = self.status_message
            presence = xmpp.Presence()
            presence.setStatus(new_status)
            self.conn.send(presence)

        self.plugin.waiting_muc_messages = []
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

    def GoOn(self):
        while self.StepOn(): pass

    # callback handlers
    def message_callback(self, conn, message):
        realjid = self.cfg_jid
        if message.__getitem__('type') == 'groupchat':
            try:
                realjid = self.muc_users[str(message.getFrom())]
            except KeyError:
                # recieved a message from a user which is probably not here anymore
                pass
        elif message.__getitem__('type') == 'chat':
            realjid = str(message.getFrom()).split('/')[0]

        # check if it is a message from myself
        if self.cfg_jid != realjid:
            admin = None
            # check if the user is a admin
            for (jid, username) in self.users:
                if jid == realjid:
                    admin = username

            if admin:
                self.plugin.core.add_timeout(0, self.plugin.on_authorized_xmpp_message, message, realjid)
            else:
                self.plugin.core.add_timeout(0, self.plugin.on_unauthorized_xmpp_message, message, realjid)

    def disconnect_callback(self, conn, message):
        self.logger.info("Jabber worker disconnect callback called!")
        self.xmpp_disconnect()
        
    def iq_callback(self, conn, message):
        # self.logger.debug("iq") # callback: %s" % message)
        if message.getType() == 'get':
            pass
        else:
            # self.logger.debug("iq event callback from %s to %s!" % (message.getFrom(), message.getTo()))
            if message.getType() == 'result':
                # self.logger.debug(message.getAttrs())
                pass
            elif message.getType() == 'error':
                # self.logger.debug(message.getAttrs())
                pass

    def presence_callback(self, conn, message):
        prs_type = message.getType()
        who = str(message.getFrom())
        if prs_type == 'subscribe':
                self.conn.send(xmpp.Presence(to=who, typ = 'subscribed'))
                self.conn.send(xmpp.Presence(to=who, typ = 'subscribe'))
        elif prs_type == 'presence':
            self.logger.debug("::: %s" % msg.__getitem__('jid'))
        else:
            if message.getJid():
                src_jid = self.plugin.core.utils.convert_from_unicode(message.getJid()).split('/')
                self.muc_users[who] = src_jid[0]

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
        self.waiting_muc_messages = []
        self.users = []
        self.jabber_status_string = ''
        self.proximity_status_string = ''
        self.nodes_online_num = 0
        self.show_broadcast = False
        self.start_time = int(time.time())
        self.last_xmpp_status_message = ''

        self.commands.create_subcommand('list', 'Lists all allowed Jabber users', self.cmd_list_users)
        broadcase_cmd = self.commands.create_subcommand('broadcast', 'Should broadcast messages be sent', None)
        broadcase_cmd.create_subcommand('on', 'Activates broadcast messages', self.cmd_broadcast_on)
        broadcase_cmd.create_subcommand('off', 'Deactivates broadcast messages', self.cmd_broadcast_off)

    # plugin methods
    def start(self):
        for person in self.core.config['persons'].keys():
            try:
                self.users.append((self.core.config['persons'][person]['jid'], person))
            except Exception:
                pass

        # generate initial staus
        if self.core.proximity_status.status[self.core.location]:
            self.proximity_status_string = "You are at home"
        else:
            self.proximity_status_string = "You are away"
        self.process_discovery_event(None)
        self.set_jabber_status()

        self.start_worker()
    
    def terminate(self):
        self.worker_must_exit()

    # james command methods
    def cmd_list_users(self, args):
        ret = []
        for (jid, name) in self.users:
            ret.append("%-15s %s" % (jid, name))
        return ret

    def cmd_broadcast_on(self, args):
        self.show_broadcast = True
        return ["Broadcast messages will be shown"]

    def cmd_broadcast_off(self, args):
        self.show_broadcast = False
        return ["Broadcast messages will no longer be shown"]

    # methods for worker process
    def send_xmpp_message(self, message_head = [], message_body = [], to = None):
        self.worker_lock.acquire()
        self.waiting_messages.append((message_head, message_body, to))
        self.worker_lock.release()

    def send_xmpp_muc_message(self, message_head = [], message_body = []):
        self.worker_lock.acquire()
        self.waiting_muc_messages.append((message_head, message_body))
        self.worker_lock.release()

    def change_xmpp_status_message(self, new_message):
        self.worker_lock.acquire()
        self.jabber_status_string = new_message
        self.worker_lock.release()

    # worker callback methods
    def on_worker_exit(self):
        self.logger.info('XMPP worker exited')

    def on_authorized_xmpp_message(self, message, realjid):
        msg_types = {'chat'      : self.on_chat_msg,
                     'error'     : self.on_error_msg,
                     'groupchat' : self.on_groupchat_msg}

        try:
            msg_types[message.__getitem__('type')](message)
        except KeyError:
            self.logger.debug("Recieved unkonwn message type: %s" % message.__getitem__('type'))
            pass

    def on_unauthorized_xmpp_message(self, message, realjid):
        # for the first 3 seconds, ignore groupchat messages
        # (the server sends the last X messages, so do not process them multiple times)
        if (self.start_time + 3) < int(time.time()):
            bad_user = str(message.getFrom()).split('/')[1]
            self.send_xmpp_muc_message(['%s (%s), you are not authorized!' % (bad_user, realjid)])

    def on_chat_msg(self, message):
        jid_data = str(message.getFrom()).split('/')
        jid_from = jid_data[0]
        try:
            jid_ress = jid_data[1]

            command = self.core.utils.list_unicode_cleanup(message.getBody().split())
            # compensate for first auto capital letter on many mobile devices
            command[0] = command[0].lower()
            self.run_command(command, jid_from)
        except IndexError:
   			return ["No command submitted"]
        except AttributeError:
			return ["No command submitted"]

    def on_groupchat_msg(self, message):
        # for the first 3 seconds, ignore groupchat messages
        # (the server sends the last X messages, so do not process them multiple times)
        if (self.start_time + 3) < int(time.time()):
            jid_data = str(message.getFrom()).split('/')
            jid_from = jid_data[1]
            # ignore my own messages
            if not jid_from == self.core.config['jabber']['muc_nick']:
                try:
                    jid_ress = jid_data[1]

                    command = self.core.utils.list_unicode_cleanup(message.getBody().split())
                    # compensate for first auto capital letter on many mobile devices
                    command[0] = command[0].lower()
                    self.run_muc_command(command)
                except IndexError:
                    pass
                pass

    def on_error_msg(self, message):
        # self.logger.error("Recieved error msg: %s" % message)
        pass

    # worker callback helper methods
    def run_command(self, command, jid_from):
        if command[0] == 'help':
            help_text = self.jabber_cmd_help(command[1:])
            self.send_xmpp_message(['Commands are:'], help_text, jid_from)
        else:
            self.send_command(command)

    def run_muc_command(self, command):
        if command[0] == 'help':
            help_text = self.jabber_cmd_help(command[1:])
            self.send_xmpp_muc_message(['Commands are:'], help_text)
        else:
            self.send_command(command)

    # worker process help methods
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

    # worker control methods
    def start_worker(self):
        # FIXME make me singleton!
        self.worker_lock.acquire()
        self.worker_exit = False
        self.worker_lock.release()

        cleaned_users = self.users
        try:
            cleaned_users = self.core.utils.convert_from_unicode(self.users)
        except RuntimeError:
            pass

        self.rasp_thread = JabberThread(self,
                                        cleaned_users,
                                        self.core.config['jabber']['jid'],
                                        self.core.config['jabber']['password'],
                                        self.core.config['jabber']['muc_room'],
                                        self.core.config['jabber']['muc_nick'])
        self.rasp_thread.start()
        self.logger.info('XMPP worker starting')
        return 'XMPP worker starting'

    def worker_must_exit(self):
        self.worker_lock.acquire()
        self.worker_exit = True
        self.worker_lock.release()
        self.logger.debug('XMPP worker exiting')
        return 'XMPP worker exiting'

    # plugin event methods
    def process_command_response(self, args, host, plugin):
        message = ['Direct:']
        for line in args:
            message.append("%10s@%-10s: %s" % (plugin, host, line))
        self.send_xmpp_muc_message(message)
        if not self.core.proximity_status.status[self.core.location]:
            self.send_xmpp_message(message)

    def process_broadcast_command_response(self, args, host, plugin):
        message = ['Broadcast:']
        for line in args:
            message.append("%10s@%-10s: %s" % (plugin, host, line))
        self.send_xmpp_muc_message(message)

        send_msg = False
        if self.show_broadcast:
            send_msg = True
        if not self.core.proximity_status.status[self.core.location]:
            send_msg = True
        if send_msg:
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
        self.logger.debug("Processing proximity event")
        if newstatus['status'][self.core.location]:
            self.proximity_status_string = "You are at home"
            self.set_jabber_status()
        else:
            self.proximity_status_string = "You are away"
            self.set_jabber_status()

    def process_discovery_event(self, msg):
        if msg:
            if msg[0] == 'nodes_online' or msg[0] == 'byebye' or msg[0] == 'hello':
                self.nodes_online_num = len(self.core.nodes_online)
                self.set_jabber_status()

    def set_jabber_status(self):
        message = "%s. %s nodes online." % (self.proximity_status_string,
                                            self.nodes_online_num)
        if self.last_xmpp_status_message != message:
            self.logger.debug('Setting status message to (%s)' % message)
            self.change_xmpp_status_message(message)
            self.last_xmpp_status_message = message


descriptor = {
    'name' : 'jabber',
    'help' : 'Interface to Jabber (XMPP))',
    'command' : 'jab',
    'mode' : PluginMode.MANAGED,
    'class' : JabberPlugin
}
