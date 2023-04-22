import transmissionrpc

from james.plugin import *

from src.james.plugin import Plugin, PluginMode


# https://bitbucket.org/blueluna/transmissionrpc/wiki/Home


class TransmissionPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(TransmissionPlugin, self).__init__(core, descriptor)

        self.muted_words = self.utils.list_unicode_cleanup(self.config['dont_say'])
        self.server_string = "%s@%s:%s" % (self.config['nodes'][self.core.hostname]['username'],
                                           self.config['nodes'][self.core.hostname]['host'],
                                           self.config['nodes'][self.core.hostname]['port'])

        self.tr_conn = None
        self.addedTorrents = 0
        self.finishedTorrents = 0
        self.load_state('addedTorrents', 0)
        self.load_state('finishedTorrents', 0)

        self.commands.create_subcommand('show', 'Shows a list current torrents', self.cmd_show)
        self.commands.create_subcommand('add', 'Adds a URL to download', self.cmd_add)
        self.commands.create_subcommand('start', 'Restart a torrent', self.cmd_start)
        self.commands.create_subcommand('force', 'Force download a torrent', self.cmd_force)
        self.commands.create_subcommand('stop', 'Stops a torrent', self.cmd_stop)
        self.commands.create_subcommand('remove', 'Removes a torrent', self.cmd_remove)
        self.commands.create_subcommand('test', 'Checks if the connection to the transmission host is working',
                                        self.cmd_test_connection)

    def connect(self):
        try:
            self.tr_conn = transmissionrpc.Client(address=self.config['nodes'][self.core.hostname]['host'],
                                                  port=self.config['nodes'][self.core.hostname]['port'],
                                                  user=self.config['nodes'][self.core.hostname]['username'],
                                                  password=self.config['nodes'][self.core.hostname]['password'],
                                                  timeout=5)
            return True
        except Exception as e:
            return False

    def connection_ok(self):
        try:
            tmp_all = self.tr_conn.get_status_all()
            return True
        except Exception as e:
            return self.connect()

    def start(self):
        self.worker_loop()

    def cmd_show(self, args):
        def candy_output(tid, qpos, status, rate, peers, eta, ratio, name):
            if isinstance(ratio, float):
                ratio = round(ratio, 3)
            elif isinstance(ratio, int):
                if int(ratio) <= 0:
                    ratio = "-"

            if rate == "0B":
                rate = "-"

            if peers == 0:
                peers = "-"

            return "%3s %5s %-18s %10s %6s %9s %8s %s" % (tid, qpos, status.rstrip(), rate.lstrip().rstrip(), peers,
                                                          eta, ratio, name)

        ret = []
        if self.connection_ok():
            ret.append("Currently available torrents:")

            ret.append(candy_output("ID", "Q Pos", "Status", "DL Speed", "Peers", "Remaining", "UL Ratio", "Name"))
            for torrent_id in self.tr_conn.get_files():
                torrent = self.tr_conn.info(torrent_id)[torrent_id]

                try:
                    my_eta = torrent.eta
                except ValueError:
                    my_eta = "-"

                dl_rate = self.utils.bytes2human(torrent.rateDownload)
                # with this code block you see all the attributes of the torrent
                # for key, value in torrent.fields.iteritems():
                #     self.logger.debug(key, value)
                ret.append(candy_output(torrent_id, torrent.queue_position, torrent.status,
                                        dl_rate, torrent.peersConnected, my_eta, torrent.uploadRatio, torrent.name))
        else:
            self.logger.warning("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
            ret.append("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
        return ret

    def cmd_add(self, args):
        if self.connection_ok():
            args = self.utils.list_unicode_cleanup(args)
            try:
                self.tr_conn.add_uri(args[0])
                self.addedTorrents += 1
                self.logger.info('Download of (%s) starting' % args[0])
                self.send_command(['jab', 'msg', 'Torrent download started'])
                return ["Torrent added"]
            except transmissionrpc.TransmissionError as e:
                self.logger.warning('Torrent download not started due error (%s)' % args[0])
                self.send_command(['jab', 'msg', 'Torrent download not started due error (%s)' % args[0]])
                pass
            except IndexError:
                return ["Syntax error!"]
                pass

        else:
            return ["ERROR: Unable to connect to transmission host (%s)" % self.server_string]

    def cmd_remove(self, args):
        ret = []
        if self.connection_ok():
            args = self.utils.list_unicode_cleanup(args)
            for t_id in args:
                try:
                    self.tr_conn.remove(int(t_id))
                    ret.append("Removed Torrent ID: %s" % t_id)
                except Exception:
                    ret.append("Unable to remove Torrent ID: %s" % t_id)
                    pass
        else:
            ret.append("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
        return ret

    def cmd_force(self, args):
        ret = []
        if self.connection_ok():
            args = self.utils.list_unicode_cleanup(args)
            for t_id in args:
                try:
                    self.tr_conn.start(int(t_id), bypass_queue=True)
                    self.logger.info("Force started Torrent ID: %s" % t_id)
                    ret.append("Force started Torrent ID: %s" % t_id)
                except Exception:
                    self.logger.warning("Unable to force start Torrent ID: %s" % t_id)
                    ret.append("Unable to force start Torrent ID: %s" % t_id)
                    pass
        else:
            self.logger.warning("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
            ret.append("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
        return ret

    def cmd_start(self, args):
        ret = []
        if self.connection_ok():
            args = self.utils.list_unicode_cleanup(args)
            for t_id in args:
                try:
                    self.tr_conn.start(int(t_id))
                    self.logger.info("Started Torrent ID: %s" % t_id)
                    ret.append("Started Torrent ID: %s" % t_id)
                except Exception:
                    self.logger.warning("Unable to start Torrent ID: %s" % t_id)
                    ret.append("Unable to start Torrent ID: %s" % t_id)
                    pass
        else:
            self.logger.warning("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
            ret.append("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
        return ret

    def cmd_stop(self, args):
        ret = []
        if self.connection_ok():
            args = self.utils.list_unicode_cleanup(args)
            for t_id in args:
                try:
                    self.tr_conn.stop(int(t_id))
                    ret.append("Stopped Torrent ID: %s" % t_id)
                except Exception:
                    ret.append("Unable to stop Torrent ID: %s" % t_id)
                    pass
            return ret
        else:
            self.logger.warning("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
            ret.append("ERROR: Unable to connect to transmission host (%s)" % self.server_string)

    def worker_loop(self):
        if self.connection_ok():
            try:
                for torrent_id in self.tr_conn.get_files():
                    torrent = self.tr_conn.info(torrent_id)[torrent_id]
                    if torrent.isFinished and torrent.status == 'stopped' and torrent.percentDone == 1 \
                            and torrent.leftUntilDone == 0 and torrent.progress == 100:
                        newname = self.remove_muted_words(torrent.name)
                        self.logger.info("Download of %s finished" % newname)
                        self.send_command(['jab', 'msg', 'Torrent of %s finished' % newname])
                        self.tr_conn.remove(torrent_id)
                        self.finishedTorrents += 1
            except ValueError:
                self.logger.warning("FIXME: Strange ValueError occurred. FIX ME MASTER!")
            except transmissionrpc.error.TransmissionError as e:
                self.logger.warning("TransmissionError occurred: %s" % e)
            except Exception as e:
                self.logger.warning("FIXME: Strange Exception occurred. FIX ME MASTER!")
        self.core.add_timeout(self.config['nodes'][self.core.hostname]['loop_time'], self.worker_loop)

    def cmd_test_connection(self, args):
        if self.connection_ok():
            return ["Connection to %s established" % self.server_string]
        else:
            return ["Unable to connect to %s" % self.server_string]

    # helper methods
    def remove_muted_words(self, text):
        spacers = ['.', ',', '-', '_', '[', ']', '(', ')', '{', '}', '/', '\\']
        for spacer in spacers:
            text = text.replace(spacer, ' ')

        old_words = text.split(' ')
        new_words = []
        for word in old_words:
            if word.lower() not in [x.lower() for x in self.muted_words] and word:
                new_words.append(word)
        return ' '.join(new_words)

    def return_status(self, verbose=False):
        ret = {'connected': False}
        if self.connection_ok():
            ret['connected'] = True
        ret['addedTorrents'] = self.addedTorrents
        return ret


descriptor = {
    'name': 'transmission',
    'help_text': 'Transmission control plugin',
    'command': 'tr',
    'mode': PluginMode.MANAGED,
    'class': TransmissionPlugin,
    'detailsNames': {'connected': "Connected",
                     'addedTorrents': "Amount of added torrents",
                     'finishedTorrents': "Amount of finished torrents"}
}
