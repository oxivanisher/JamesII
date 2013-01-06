
import transmissionrpc

from james.plugin import *

# https://bitbucket.org/blueluna/transmissionrpc/wiki/Home

class TransmissionPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(TransmissionPlugin, self).__init__(core, descriptor)

        connected = False
        try:
            self.tr_conn = transmissionrpc.Client(address=self.core.config['transmission']['nodes'][self.core.hostname]['host'],
                                                  port=self.core.config['transmission']['nodes'][self.core.hostname]['port'],
                                                  user=self.core.config['transmission']['nodes'][self.core.hostname]['username'],
                                                  password=self.core.config['transmission']['nodes'][self.core.hostname]['password'],
                                                  timeout=5)
            connected = True
        except Exception as e:
            print("Transmission connection ERROR: %s" % e)
            pass

        if connected:
            self.commands.create_subcommand('show', 'Shows a list current torrents', self.cmd_show)
            self.commands.create_subcommand('add', 'Adds a URL to download', self.cmd_add)
            self.commands.create_subcommand('start', 'Restart a torrent', self.cmd_start)
            self.commands.create_subcommand('stop', 'Stopps a torrent', self.cmd_stop)
            self.commands.create_subcommand('remove', 'Removes a torrent', self.cmd_remove)

    def start(self):
        self.finished_loop()

    def cmd_show(self, args):
        ret = ["Currently available torrents:"]
        ret.append("%3s %-12s %9s %s" % ("ID", "Status", "Remaining", "Name"))
        for torrent_id in self.tr_conn.get_files():
            torrent =  self.tr_conn.info(torrent_id)[torrent_id]
            if not torrent.eta:
                my_eta = "-"
            else:
                my_eta = torrent.eta
            ret.append("%3s %-12s %9s %s" % (torrent_id, torrent.status, my_eta, torrent.name))
        return ret

    def cmd_add(self, args):
        args = self.core.utils.list_unicode_cleanup(args)
        try:
            self.tr_conn.add_uri(args[0])
            return ["Torrent added"]
        except transmissionrpc.TransmissionError as e:
            print(e.message)
            return ["Torrent not added (%s)" % e.message]
            pass

    def cmd_remove(self, args):
        args = self.core.utils.list_unicode_cleanup(args)
        ret = []
        for t_id in args:
            try:
                self.tr_conn.remove(int(t_id))
                ret.append("Removed Torrent ID: %s" % t_id)
            except Exception:
                ret.append("Unable to remove Torrent ID: %s" % t_id)
                pass
        return ret

    def cmd_start(self, args):
        args = self.core.utils.list_unicode_cleanup(args)
        ret = []
        for t_id in args:
            try:
                self.tr_conn.start(int(t_id))
                ret.append("Started Torrent ID: %s" % t_id)
            except Exception:
                ret.append("Unable to start Torrent ID: %s" % t_id)
                pass
        return ret

    def cmd_stop(self, args):
        args = self.core.utils.list_unicode_cleanup(args)
        ret = []
        for t_id in args:
            try:
                self.tr_conn.stop(int(t_id))
                ret.append("Stopped Torrent ID: %s" % t_id)
            except Exception:
                ret.append("Unable to stop Torrent ID: %s" % t_id)
                pass
        return ret

    def finished_loop(self):
        for torrent_id in self.tr_conn.get_files():
            torrent =  self.tr_conn.info(torrent_id)[torrent_id]
            if torrent.isFinished and torrent.status == 'stopped':
                message = self.core.new_message(self.name)
                message.level = 1
                message.header = ("Download of %s finished" % torrent.name)
                message.send()
                self.tr_conn.remove(torrent_id)
        self.core.add_timeout(self.core.config['transmission']['nodes'][self.core.hostname]['loop_time'], self.finished_loop)

descriptor = {
    'name' : 'transmission',
    'help' : 'Transmission control plugin',
    'command' : 'tr',
    'mode' : PluginMode.MANAGED,
    'class' : TransmissionPlugin
}
