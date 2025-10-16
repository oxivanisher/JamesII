import threading

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

    def __init__(self, plugin, users, cfg_jid, password, muc_room=None, muc_nick='james'):
        super().__init__(plugin)
        self.cfg_jid = cfg_jid
        self.password = password
        self.active = True
        self.users = users
        self.status_message = ''
        self.muc_room = muc_room
        self.muc_nick = muc_nick
        self.conn = False
        self.roster = {}
        self.my_roster = None
        self.muc_users = {}
        self.reconnecting_loop = 0
        self.startupTime = time.time()
        self.last_ping = 0

    # jabber connection methods
    def xmpp_connect(self):
        self.logger.debug("XMPP connect called")
        # setup connection
        jid = xmpp.protocol.JID(self.cfg_jid)
        self.conn = xmpp.Client(jid.getDomain(), debug=[])  # debug can be 'always'
        conres = self.conn.connect()

        if not conres:
            self.logger.warning(f"Unable to connect to server {jid.getDomain()}!")
            self.active = False
        else:
            self.logger.info(f"Successfully connect to server {jid.getDomain()}!")
            self.active = True

        if self.active:
            if conres != 'tls':
                self.logger.warning("Unable to establish secure connection - TLS failed!")

            authres = self.conn.auth(jid.getNode(), self.password, resource=jid.getResource())

            if not authres:
                self.logger.error(f"Unable to authorize on {jid.getDomain()} - check login/password.")
                self.active = False
            if authres != 'sasl':
                self.logger.warning(
                    f"Warning: unable to perform SASL auth on {jid.getDomain()}. Old authentication method used!")

            # lets go online
            self.conn.sendInitPresence(requestRoster=1)
            self.my_roster = self.conn.getRoster()

            # registering handlers
            self.conn.RegisterHandler('msg', self.message_callback)
            self.conn.RegisterHandler('presence', self.presence_callback)
            self.conn.RegisterHandler('disconnect', self.disconnect_callback)
            self.conn.RegisterHandler('iq', self.iq_callback)

            self.connect_to_room()

            # get our roster
            my_roster = self.conn.getRoster()
            for i in my_roster.getItems():
                self.roster[i] = my_roster.getStatus(i)
            if self.roster:
                self.roster = self.plugin.utils.convert_from_unicode(self.roster)

            # self.logger.debug("Jabber worker roster: %s" % self.roster)
            self.reconnecting_loop = 0
            return True

        else:
            # unable to connect to server
            self.xmpp_disconnect()
            return False

    def xmpp_disconnect(self):
        self.logger.info("Jabber worker disconnect called!")
        self.plugin.worker_lock.acquire()
        worker_exit = self.plugin.worker_exit
        self.plugin.worker_lock.release()
        self.roster = {}
        if not worker_exit:
            try:
                while not self.conn.reconnectAndReauth():
                    time.sleep(5)
            except Exception:
                self.conn = False
                if not self.reconnecting_loop > 12:
                    self.reconnecting_loop += 1
                if self.reconnecting_loop > 1:
                    self.logger.info(f"Jabber worker reconnect delay: {self.reconnecting_loop * 5}")
                    time.sleep(self.reconnecting_loop * 5)
            self.xmpp_connect()
        else:
            self.active = False

    # connect to room
    def connect_to_room(self):
        # do we have to connect to a muc room?
        if self.muc_room:
            self.conn.send(xmpp.Presence(to=f'{self.muc_room}/{self.muc_nick}'))

        # resend status msg
        new_status = self.status_message
        presence = xmpp.Presence()
        presence.setStatus(new_status)
        self.conn.send(presence)

    # base worker methods
    def work(self):
        if self.xmpp_connect():
            # dive into the endless loops
            self.go_on()
        else:
            self.plugin.worker_lock.acquire()
            worker_exit = self.plugin.worker_exit
            self.plugin.worker_lock.release()
            if not worker_exit:
                time.sleep(2)
                self.work()
            else:
                self.active = False

    def step_on(self):
        try:
            if time.time() - self.last_ping > 10:
                self.last_ping = time.time()
                ping = xmpp.Protocol('iq', typ='get', payload=[xmpp.Node('ping', attrs={'xmlns': 'urn:xmpp:ping'})])
                ping_res = self.conn.SendAndWaitForResponse(ping, 1)
                if not ping_res:
                    self.xmpp_disconnect()

            res = self.conn.Process(1)
            if res == '0':
                # Nothing happened, everything is ok
                pass
            elif res == 0:
                self.logger.debug("Underlying connection is closed on processing incoming stanzas")
                self.xmpp_disconnect()

        except IOError:
            self.logger.debug("IOError on processing incoming stanzas")
            self.xmpp_disconnect()
        except Exception as e:
            self.logger.info(f"Error {e} on processing incoming stanzas. Disconnecting")
            self.xmpp_disconnect()

        if not self.conn.isConnected():
            self.xmpp_disconnect()

        self.plugin.worker_lock.acquire()

        # see if I must shut myself down
        if self.plugin.worker_exit:
            self.active = False
        # see if we must send muc messages
        if self.muc_room:
            muc_user_jids = []
            amount_users = len(self.users)
            for muc_user in self.muc_users:
                try:
                    muc_user_jids.append(self.muc_users[muc_user].split('/')[0])
                except AttributeError:
                    self.logger.warning(
                        f"The bug hunt is on: Got a unparsable muc user list {self.muc_users[muc_user]}")

            for (header, body) in self.plugin.waiting_muc_messages:
                amount_chat_deliveries = 0
                for (userJid, username) in self.users:
                    if userJid not in muc_user_jids:
                        amount_chat_deliveries += 1
                        self.plugin.waiting_messages.append((header, body, userJid))
                        self.logger.debug(f"Delivering MUC msg to {userJid} via private chat")

                if amount_chat_deliveries < amount_users:
                    try:
                        msg_text = '\n'.join(header)
                        if len(body):
                            msg_text = msg_text + '\n' + '\n'.join(body)
                        msg = xmpp.protocol.Message(body=msg_text)
                        msg.setTo(self.muc_room)
                        msg.setType('groupchat')
                        self.conn.send(msg)
                        self.logger.debug(f"Send MUC msg: {msg_text}")
                    except Exception as e:
                        self.logger.warning(f"Send MUC msg ERROR: {e}")
                else:
                    self.logger.debug("Not delivering msg to MUC, all users where contacted via private msg.")
        # see if we must send direct messages
        for (header, body, to_jid) in self.plugin.waiting_messages:
            try:
                message = False
                if to_jid:
                    # msg to one user
                    message = self.create_message(to_jid, header, body)
                    self.conn.send(message)
                else:
                    # broadcast msg to every user
                    # muc_send = False
                    for (jid, name) in self.users:
                        # see if user is in muc online and then send it there only
                        for mucJid in self.muc_users:
                            try:
                                online_jid = self.plugin.utils.convert_from_unicode(self.muc_users[mucJid]).split('/')
                            except AttributeError:
                                self.logger.warning(
                                    f"The bug hunt is on: Searching for online Jid {self.plugin.utils.convert_from_unicode(self.muc_users[mucJid])}")
                            # if online_jid[0] == jid:
                            # muc_send = True
                            # else:
                            if online_jid[0] != jid:
                                message = self.create_message(jid, header, body)
                                self.conn.send(message)
                    # if muc_send:

            except Exception as e:
                self.logger.debug(f"Send direct msg ERROR: {e}")
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

    def create_message(self, to, header=None, body=None):
        header = header or []
        body = body or []
        if not header:
            return False
        message_list = [s for s in header if s != '']
        if body:
            message_list = message_list + [s for s in body if s != '']
        message_text = '\n'.join(message_list)
        message = xmpp.protocol.Message(to, message_text)
        message.setAttr('type', 'chat')
        return message

    def go_on(self):
        while self.step_on():
            pass

    # callback handlers
    def message_callback(self, conn, message):
        message_type = message.__getitem__('type')
        who = str(message.getFrom())
        self.logger.debug(f"Message callback from {who} ({message_type})")

        try:
            if message.getBody()[0] == "!":
                self.logger.debug(f"Ignoring msg starting with ! from user: {message.getFrom()}")
                return
        except Exception:
            pass

        if (time.time() - self.startupTime) < 10:
            # self.logger.info("Ignoring msg from %s due startup delay" % (msg.getFrom()))
            pass
        else:
            real_jid = None
            if message_type == 'groupchat':
                # ignoring messages from the room itself ?!?
                if who == f"{self.muc_room}/{self.muc_nick}":
                    self.logger.debug("Received MUC msg from channel and ignoring it")
                    return
                try:
                    real_jid = self.muc_users[message.getFrom()].split('/')[0]
                    self.logger.debug(f"Received MUC msg from user: {message.getFrom()}")
                except AttributeError:
                    self.logger.warning(
                        f"The bug hunt is on: Got a msg from {self.muc_users[message.getFrom()]} in groupchat")
                except Exception as e:
                    self.logger.debug(f"RealJID's DB: {self.muc_users}")
                    self.logger.info(f"Received MUC msg from non online user: {who} ({e})")
            elif message_type == 'chat':
                try:
                    real_jid = str(message.getFrom()).split('/')[0]
                    self.logger.debug(f"Received chat msg from user: {message.getFrom()}")
                except AttributeError:
                    self.logger.warning(f"The bug hunt is on: Got a msg from {message.getFrom()} in chat")

            # check if it is a msg from myself
            if real_jid:
                if str(message.getFrom()) != f"{self.muc_room}/{self.muc_nick}":
                    admin = False
                    # check if the user is a admin
                    for (userJid, username) in self.users:
                        try:
                            if userJid == real_jid.split('/')[0]:
                                admin = True
                        except AttributeError:
                            self.logger.warning(
                                f"The bug hunt is on: Unable to check for admin permissions for {real_jid}")

                    if admin:
                        self.logger.debug(f"Processing authorized msg from user {message.getFrom()}")
                        self.plugin.core.add_timeout(0, self.plugin.on_authorized_xmpp_message, message, real_jid)
                    elif real_jid in self.config['ignored']:
                        # ignored user
                        self.logger.debug(f"Ignoring msg from user {message.getFrom()}")
                    else:
                        self.logger.warning(f"Processing unauthorized msg from user {message.getFrom()}")
                        self.plugin.core.add_timeout(0, self.plugin.on_unauthorized_xmpp_message, message, real_jid)

    def disconnect_callback(self, conn, message):
        self.logger.debug("Jabber worker disconnect callback called!")
        self.xmpp_disconnect()

    def iq_callback(self, conn, iq):
        iq_type = iq.getType()
        who = str(iq.getFrom())
        self.logger.debug(f"Presence callback from {who} ({iq_type})")
        # self.logger.debug("iq") # callback: %s" % msg)
        if iq_type == 'get':
            pass
        else:
            # self.logger.debug("iq event callback from %s to %s!" % (msg.getFrom(), msg.getTo()))
            if iq_type == 'result':
                # self.logger.debug(msg.getAttrs())
                pass
            elif iq_type == 'error':
                # self.logger.debug(msg.getAttrs())
                pass

    def presence_callback(self, conn, presence):
        prs_type = presence.getType()
        who = str(presence.getFrom())
        # src_jid = self.plugin.utils.convert_from_unicode(presence.getJid()).split('/')
        self.logger.debug(f"Presence callback from {who} ({prs_type})")

        if prs_type == 'subscribe':
            self.conn.send(xmpp.Presence(to=who, typ='subscribed'))
            self.conn.send(xmpp.Presence(to=who, typ='subscribe'))
        # elif prs_type == 'presence':
        #     self.logger.debug("::: %s" % msg.__getitem__('jid'))
        elif prs_type == 'unavailable':
            self.logger.debug(f"Remove online user: {who}")
            try:
                del self.muc_users[who]
            except Exception as e:
                self.logger.debug(f"Remove online user error: {e}")
        else:
            if presence.getJid():
                if who != f"{self.muc_room}/{self.muc_nick}":
                    status = self.my_roster.getShow(presence.getJid())
                    if status in [None, 'chat']:
                        self.logger.debug(f"User now available (online, chat): {who}")
                        # self.muc_users[who] = src_jid[0]
                        self.muc_users[who] = presence.getJid()
                    elif status in ['xa', 'away', 'dnd']:
                        self.logger.debug(f"User now unavailable (offline, afk, dnd): {who}")
                        try:
                            del self.muc_users[who]
                        except Exception as e:
                            self.logger.debug(f"Remove online user error: {e}")
        self.logger.debug(f"Users online: {' '.join(self.muc_users)}")

    # called when the worker ends
    def on_exit(self, result):
        self.plugin.on_worker_exit()


class JabberPlugin(Plugin):

    def __init__(self, core, descriptor):

        super().__init__(core, descriptor)

        self.jabberThread = False
        self.worker_exit = False
        self.worker_lock = threading.Lock()
        self.waiting_messages = []
        self.waiting_muc_messages = []
        self.users = []
        self.jabber_status_string = ''
        self.presence_status_string = ''
        self.nodes_online_num = 0
        self.show_broadcast = False
        self.start_time = int(time.time())
        self.last_xmpp_status_message = ''

        self.load_state('receivedMuc', 0)
        self.load_state('receivedChat', 0)
        self.load_state('sentMuc', 0)
        self.load_state('sentChat', 0)
        self.load_state('commandsRunMuc', 0)
        self.load_state('commandsRunChat', 0)
        self.load_state('statusChanges', 0)
        self.load_state('unauthMessages', 0)

        self.commands.create_subcommand('list', 'Lists all allowed Jabber users', self.cmd_list_users)
        self.commands.create_subcommand('msg', 'Sends a msg to like alert', self.cmd_msg)
        broadcast_cmd = self.commands.create_subcommand('broadcast', 'Should broadcast messages be sent', None)
        broadcast_cmd.create_subcommand('on', 'Activates broadcast messages', self.cmd_broadcast_on)
        broadcast_cmd.create_subcommand('off', 'Deactivates broadcast messages', self.cmd_broadcast_off)

    # plugin methods
    def start(self):
        for person in self.core.config['persons']:
            try:
                self.users.append((self.core.config['persons'][person]['jid'], person))
            except Exception:
                pass

        # generate initial staus
        if len(self.core.get_present_users_here()):
            self.presence_status_string = "You are at home"
        else:
            self.presence_status_string = "You are away"
        self.process_discovery_event(None)
        self.set_jabber_status()

        self.start_worker()

    def terminate(self):
        self.worker_must_exit()

    # james command methods
    def cmd_list_users(self, args):
        ret = []
        for (jid, name) in self.users:
            ret.append(f"{jid:<15} {name}")
        return ret

    def cmd_broadcast_on(self, args):
        self.show_broadcast = True
        return ["Broadcast messages will be shown"]

    def cmd_broadcast_off(self, args):
        self.show_broadcast = False
        return ["Broadcast messages will no longer be shown"]

    def cmd_msg(self, args):
        msg = ' '.join(args)
        self.logger.debug(f'Sending msg ({msg})')
        self.send_xmpp_muc_message([f'Message: {msg}'])
        return ["Message sent"]

    # methods for worker process
    def send_xmpp_message(self, message_head=None, message_body=None, to=None):
        message_head = message_head or []
        message_body = message_body or []
        self.sentChat += 1
        self.worker_lock.acquire()
        self.waiting_messages.append((message_head, message_body, to))
        self.worker_lock.release()

    def send_xmpp_muc_message(self, message_head=None, message_body=None):
        message_head = message_head or []
        message_body = message_body or []
        self.sentMuc += 1
        self.worker_lock.acquire()
        self.waiting_muc_messages.append((message_head, message_body))
        self.worker_lock.release()

    def change_xmpp_status_message(self, new_message):
        self.statusChanges += 1
        self.worker_lock.acquire()
        self.jabber_status_string = new_message
        self.worker_lock.release()

    # worker callback methods
    def on_worker_exit(self):
        self.logger.info('XMPP worker exited')

    def on_authorized_xmpp_message(self, message, realjid):
        msg_types = {'chat': self.on_chat_msg,
                     'error': self.on_error_msg,
                     'groupchat': self.on_groupchat_msg}

        try:
            msg_types[message.__getitem__('type')](message)
        except KeyError:
            self.logger.debug(f"Received unknown msg type: {message.__getitem__('type')}")
            pass

    def on_unauthorized_xmpp_message(self, message, realjid):
        # for the first 3 seconds, ignore groupchat messages
        # (the server sends the last X messages, so do not process them multiple times)
        if (self.start_time + 3) < int(time.time()):
            self.unauthMessages += 1
            try:
                bad_user = str(message.getFrom()).split('/')[1]
                self.send_xmpp_muc_message([f'{bad_user} ({realjid}), you are not authorized!'])
            except AttributeError:
                self.logger.warning(f"The bug hunt is on: Got a unauthorized msg from {message.getFrom()}")

    def on_chat_msg(self, message):
        self.receivedChat += 1
        try:
            jid_data = str(message.getFrom()).split('/')
            jid_from = jid_data[0]
        except AttributeError:
            self.logger.warning(f"The bug hunt is on: Got a chat msg from {message.getFrom()}")
        try:
            jid_ress = jid_data[1]

            command = self.utils.list_unicode_cleanup(message.getBody().split())
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
            self.receivedMuc += 1
            try:
                jid_data = str(message.getFrom()).split('/')
                jid_from = jid_data[1]
            except AttributeError:
                self.logger.warning(f"The bug hunt is on: Got a group chat msg from {message.getFrom()}")
            # ignore my own messages
            if not message.getBody():
                self.logger.debug("Received empty group chat msg")
            elif not jid_from == self.config['muc_nick']:
                try:
                    jid_ress = jid_data[1]

                    command = self.utils.list_unicode_cleanup(message.getBody().split())
                    # compensate for first auto capital letter on many mobile devices
                    command[0] = command[0].lower()

                    self.run_muc_command(command)
                except IndexError:
                    pass
                except AttributeError:
                    self.logger.warning(f"The bug hunt is on: Got a muc_nic msg ({message.getBody()}) from {jid_from}")

    def on_error_msg(self, message):
        self.logger.error(f"Received error msg: {message}")
        pass

    # worker callback helper methods
    def run_command(self, command, jid_from):
        self.commandsRunChat += 1
        if command[0] == 'help':
            help_text = self.jabber_cmd_help(command[1:])
            self.send_xmpp_message(['Commands are:'], help_text, jid_from)
        elif command[0] in self.core.config['core']['command_aliases']:
            self.send_command(command)
        else:
            best_match = self.core.ghost_commands.get_best_match(command)
            if best_match == self.core.ghost_commands:
                command = ['help'] + command
            else:
                if best_match.subcommands:
                    command = ['help'] + command
            if command[0] == 'help':
                help_text = self.jabber_cmd_help(command[1:])
                header_text = [f'Subcommands for ({best_match.name}) are:']
                if best_match == self.core.ghost_commands:
                    header_text = ['Commands are:']

                self.send_xmpp_message(header_text, help_text, jid_from)
            else:
                self.send_command(command)

    def run_muc_command(self, command):
        self.commandsRunMuc += 1
        if command[0] == 'help':
            help_text = self.jabber_cmd_help(command[1:])
            help_text.append(f"{'+':<20} Command Aliases")
            for command in sorted(self.core.config['core']['command_aliases'].keys()):
                help_text.append(f"|- {command:<17} {self.core.config['core']['command_aliases'][command]}")
            self.send_xmpp_muc_message(['Commands are:'], help_text)
        elif command[0] in self.core.config['core']['command_aliases']:
            self.send_command(command)
        else:
            best_match = self.core.ghost_commands.get_best_match(command)
            if best_match == self.core.ghost_commands:
                command = ['help'] + command
            else:
                if best_match.subcommands:
                    command = ['help'] + command
            if command[0] == 'help':
                help_text = self.jabber_cmd_help(command[1:])
                header_text = [f'Subcommands for ({best_match.name}) are:']
                if best_match == self.core.ghost_commands:
                    header_text = ['Commands are:']
                    help_text.append(f"{'+':<20} Command Aliases")
                    for command in sorted(self.core.config['core']['command_aliases'].keys()):
                        help_text.append(
                            f"|- {command:<17} {self.core.config['core']['command_aliases'][command]}")

                self.send_xmpp_muc_message(header_text, help_text)
            else:
                self.send_command(command)

    # worker process help_text methods
    def jabber_cmd_help(self, args):
        ret = []
        if args:
            command = self.core.ghost_commands.get_best_match(args)
            if command:
                if command.help:
                    ret.append(f"{command.help}:")
                ret.append(f"{'Command:':<20} Description:")
                for line in self.return_command_help_lines(command):
                    ret.append(line)
            else:
                ret.append("Command not found")
        else:
            ret.append(f"{'Command:':<20} Description:")
            for line in self.return_command_help_lines(self.core.ghost_commands, 1):
                ret.append(line)
        return ret

    def return_command_help_lines(self, command_obj, depth=0):
        ret = []
        for command in sorted(command_obj.subcommands.keys()):
            c = command_obj.subcommands[command]
            if not c.hide:
                ret.append(f"|{depth * '-' + ' ' + c.name:<19} {c.help}")
                if c.subcommands:
                    for line in self.return_command_help_lines(c, depth + 1):
                        ret.append(line)
        return ret

    # worker control methods
    def start_worker(self):
        self.worker_lock.acquire()
        self.worker_exit = False
        self.worker_lock.release()

        cleaned_users = self.users
        try:
            cleaned_users = self.utils.convert_from_unicode(self.users)
        except RuntimeError:
            pass

        self.jabberThread = JabberThread(self,
                                         cleaned_users,
                                         self.config['jid'],
                                         self.config['password'],
                                         self.config['muc_room'],
                                         self.config['muc_nick'])
        self.jabberThread.start()
        self.logger.debug(f"Spawned worker for XMPP {self.jabberThread.name} with PID {self.jabberThread.native_id}")
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
            message.append(f"{plugin:>10}@{host:<10}: {line}")
        self.send_xmpp_muc_message(message)
        # if not len(self.core.get_present_users_here()):
        #     self.send_xmpp_message(msg)

    def process_broadcast_command_response(self, args, host, plugin):
        message = ['Broadcast:']
        for line in args:
            message.append(f"{plugin:>10}@{host:<10}: {line}")
        self.send_xmpp_muc_message(message)

        send_msg = False
        if self.show_broadcast:
            send_msg = True
        if not len(self.core.get_present_users_here()):
            send_msg = True
        if send_msg:
            self.send_xmpp_message(message)

    def process_message(self, message):
        if message.level > 1:
            message_text = [f'Message with level {message.level} from {message.sender_name}@{message.sender_host}:']
            for line in self.utils.list_unicode_cleanup([message.header]):
                message_text.append(line)
            try:
                for line in self.utils.list_unicode_cleanup([message.body]):
                    message_text.append(line)
            except Exception:
                pass
            self.send_xmpp_message(message_text)

    def process_presence_event(self, presence_before, presence_now):
        self.logger.debug("Processing presence event")
        if len(presence_now):
            self.presence_status_string = "You are at home"
            self.set_jabber_status()
        else:
            self.presence_status_string = "You are away"
            self.set_jabber_status()

    def process_discovery_event(self, msg):
        if msg:
            if msg[0] == 'nodes_online' or msg[0] == 'byebye' or msg[0] == 'hello':
                self.nodes_online_num = len(self.core.nodes_online)
                self.core.add_timeout(0, self.set_jabber_status)

    def set_jabber_status(self):
        message = f"{self.presence_status_string}. {self.nodes_online_num} nodes online."
        if self.last_xmpp_status_message != message:
            self.logger.debug(f'Setting status msg to ({message})')
            self.change_xmpp_status_message(message)
            self.last_xmpp_status_message = message

    def alert(self, args):
        if not len(self.core.get_present_users_here()):
            msg = ' '.join(args)
            self.logger.debug(f'Alerting ({msg})')
            self.send_xmpp_muc_message([f'Alert: {msg}'])

    def return_status(self, verbose=False):
        ret = {'receivedMuc': self.receivedMuc, 'receivedChat': self.receivedChat, 'sentMuc': self.sentMuc,
               'sentChat': self.sentChat, 'statusChanges': self.statusChanges, 'unauthMessages': self.unauthMessages,
               'commandsRunMuc': self.commandsRunMuc, 'commandsRunChat': self.commandsRunChat, 'online': False}

        try:
            ret['online'] = self.jabberThread.active
        except Exception:
            pass
        return ret


descriptor = {
    'name': 'jabber',
    'help_text': 'Interface to Jabber (XMPP))',
    'command': 'jab',
    'mode': PluginMode.MANAGED,
    'class': JabberPlugin,
    'detailsNames': {'receivedMuc': "Received MUC messages",
                     'receivedChat': "Received chat messages",
                     'sentMuc': "Sent chat messages",
                     'sentChat': "Sent chat messages",
                     'statusChanges': "Status changes",
                     'unauthMessages': "Unauthorized messages",
                     'commandsRunMuc': "MUC commands run",
                     'commandsRunChat': "Chat commands run",
                     'online': "Online"}
}
