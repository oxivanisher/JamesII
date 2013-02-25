
import transmissionrpc

from james.plugin import *

# https://bitbucket.org/blueluna/transmissionrpc/wiki/Home

class TransmissionPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(TransmissionPlugin, self).__init__(core, descriptor)

        self.muted_words = self.core.utils.list_unicode_cleanup(self.core.config['transmission']['dont_say'])
        self.server_string = "%s@%s:%s" % (self.core.config['transmission']['nodes'][self.core.hostname]['username'],
                                           self.core.config['transmission']['nodes'][self.core.hostname]['host'],
                                           self.core.config['transmission']['nodes'][self.core.hostname]['port'])

        self.tr_conn = None

        self.commands.create_subcommand('show', 'Shows a list current torrents', self.cmd_show)
        self.commands.create_subcommand('add', 'Adds a URL to download', self.cmd_add)
        self.commands.create_subcommand('start', 'Restart a torrent', self.cmd_start)
        self.commands.create_subcommand('stop', 'Stopps a torrent', self.cmd_stop)
        self.commands.create_subcommand('remove', 'Removes a torrent', self.cmd_remove)
        self.commands.create_subcommand('status', 'Checks if the connection to the transmission host is working', self.cmd_test_connection)

    def connect(self):
        try:
            self.tr_conn = transmissionrpc.Client(address=self.core.config['transmission']['nodes'][self.core.hostname]['host'],
                                                  port=self.core.config['transmission']['nodes'][self.core.hostname]['port'],
                                                  user=self.core.config['transmission']['nodes'][self.core.hostname]['username'],
                                                  password=self.core.config['transmission']['nodes'][self.core.hostname]['password'],
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
        ret = []
        if self.connection_ok():
            ret.append("Currently available torrents:")

            # (u'rateDownload', 1473000)
            # (u'peersConnected', 247)

            ret.append("%3s %-12s %10s %6s %9s %-8s %s" % ("ID",
                                                           "Status",
                                                           "DL Speed",
                                                           "Peers",
                                                           "Remaining",
                                                           "UL Ratio",
                                                           "Name"))
            for torrent_id in self.tr_conn.get_files():
                torrent =  self.tr_conn.info(torrent_id)[torrent_id]
                if not torrent.eta:
                    my_eta = "-"
                else:
                    my_eta = torrent.eta

                dl_rate = self.core.utils.bytes2human(torrent.rateDownload)
                # with this code block you see all the attributes of the torrent
                # for key, value in torrent.fields.iteritems():
                #     print(key, value)
                ret.append("%3s %-12s %8s/s %6s %9s %-8s %s" % (torrent_id,
                                                               torrent.status,
                                                               dl_rate,
                                                               torrent.peersConnected,
                                                               my_eta,
                                                               torrent.uploadRatio,
                                                               torrent.name))
        else:
            ret.append("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
        return ret

    def cmd_add(self, args):
        if self.connection_ok():
            args = self.core.utils.list_unicode_cleanup(args)
            message = self.core.new_message(self.name)
            message.level = 2
            try:
                self.tr_conn.add_uri(args[0])
                message.header = ("Torrent download started")
                message.body = args[0]
                message.send()            
                return ["Torrent added"]
            except transmissionrpc.TransmissionError as e:
                message.header = ("Torrent download not started due error")
                message.body = args[0]
                message.send()
                pass
            except IndexError:
                return ["Syntax error!"]
                pass
        else:
            return ["ERROR: Unable to connect to transmission host (%s)" % self.server_string]

    def cmd_remove(self, args):
        ret = []
        if self.connection_ok():
            args = self.core.utils.list_unicode_cleanup(args)
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

    def cmd_start(self, args):
        ret = []
        if self.connection_ok():
            args = self.core.utils.list_unicode_cleanup(args)
            for t_id in args:
                try:
                    self.tr_conn.start(int(t_id))
                    ret.append("Started Torrent ID: %s" % t_id)
                except Exception:
                    ret.append("Unable to start Torrent ID: %s" % t_id)
                    pass
        else:
            ret.append("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
        return ret

    def cmd_stop(self, args):
        ret = []
        if self.connection_ok():
            args = self.core.utils.list_unicode_cleanup(args)
            for t_id in args:
                try:
                    self.tr_conn.stop(int(t_id))
                    ret.append("Stopped Torrent ID: %s" % t_id)
                except Exception:
                    ret.append("Unable to stop Torrent ID: %s" % t_id)
                    pass
            return ret
        else:
            ret.append("ERROR: Unable to connect to transmission host (%s)" % self.server_string)
    
    def worker_loop(self):
        if self.connection_ok():
            for torrent_id in self.tr_conn.get_files():
                try:
                    torrent =  self.tr_conn.info(torrent_id)[torrent_id]
                    if torrent.isFinished and torrent.status == 'stopped':
                        newname = self.remove_muted_words(torrent.name)
                        message = self.core.new_message(self.name)
                        message.level = 2
                        message.header = ("Download of %s finished" % newname)
                        message.send()

                        self.tr_conn.remove(torrent_id)
                except ValueError:
                    print ("FIXME: Strange ValueError occured. FIX ME MASTER!")
                except transmissionrpc.error.TransmissionError as e:
                    print ("TransmissionError occured: %s" % e)
        self.core.add_timeout(self.core.config['transmission']['nodes'][self.core.hostname]['loop_time'], self.worker_loop)

    def cmd_test_connection(self, args):
        if self.connection_ok():
            return ["Connection to %s established" % self.server_string]
        else:
            return ["Unable to connect to %s" % self.server_string]

    # helper methods
    def remove_muted_words(self, text):
        spacers = ['.', ',', '-', '[', ']', '(', ')', '{', '}', '/', '\\']
        for spacer in spacers:
            text = text.replace(spacer, ' ')

        old_words = text.split(' ')
        new_words = []
        for word in old_words:
            if word.lower() not in [x.lower() for x in self.muted_words] and word:
                new_words.append(word)
        print ' '.join(new_words)
        return ' '.join(new_words)

descriptor = {
    'name' : 'transmission',
    'help' : 'Transmission control plugin',
    'command' : 'tr',
    'mode' : PluginMode.MANAGED,
    'class' : TransmissionPlugin
}
