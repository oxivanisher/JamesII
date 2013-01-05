
import xmpp

from james.plugin import *

# http://xmpppy.sourceforge.net/
class JabberThread(PluginThread):

    def __init__(self, plugin, cfg_jid, password):
        # FIXME i must become a singleton!
        super(JabberThread, self).__init__(plugin)
        self.cfg_jid = cfg_jid
        self.password = password
        active = True

    def work(self):
        jid=xmpp.protocol.JID(self.cfg_jid)
        cl=xmpp.Client(jid.getDomain(),debug=[])

        cl.connect()
        cl.auth(jid.getNode(),self.password)

        cl.sendInitialPresence()
        cl.send(xmpp.protocol.Message("oxi@oxi.ch","my test message"))

        self.plugin.worker_lock.acquire()
        # see if i must shut myself down
        if self.plugin.worker_exit:
            active = False
        self.plugin.worker_lock.release()

    def on_exit(self, result):
        pass

    # called when the worker ends
    def on_exit(self, result):
        self.plugin.on_worker_exit()

class JabberPlugin(Plugin):

    def __init__(self, core, descriptor):

        super(JabberPlugin, self).__init__(core, descriptor)

        self.rasp_thread = False
        self.worker_exit = False
        self.worker_lock = threading.Lock()

        self.commands.create_subcommand('test', 'Do some test', self.cmd_xmpp_test)

    # plugin methods
    def start(self):
        self.start_worker()
    
    def terminate(self):
        self.worker_must_exit()

    # james command methods
    def cmd_xmpp_test(self, args):
        pass

    # methods for worker process
    def on_worker_exit(self):
        self.send_broadcast(['XMPP worker exited'])

    # worker control methods
    def start_worker(self):
        # FIXME make me singleton!
        self.worker_lock.acquire()
        self.worker_exit = False
        self.worker_lock.release()
        self.rasp_thread = JabberThread(self,
                                      self.core.config['xmpp']['jid'],
                                      self.core.config['xmpp']['password'])
        self.rasp_thread.start()
        return self.send_broadcast(['XMPP worker starting'])

    def worker_must_exit(self):
        self.worker_lock.acquire()
        self.worker_exit = True
        self.worker_lock.release()
        return self.send_broadcast(['XMPP worker exiting'])

descriptor = {
    'name' : 'jabber',
    'help' : 'Interface to Jabber (XMPP))',
    'command' : 'jab',
    'mode' : PluginMode.MANAGED,
    'class' : JabberPlugin
}