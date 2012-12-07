
import bluetooth

from james.plugin import *

class ProximityPlugin(Plugin):

    def __init__(self, core):
        super(ProximityPlugin, self).__init__(core, ProximityPlugin.name)

        self.create_command('scan', self.cmd_scan, 'proximity scan')

    def terminate(self):
        pass

    def cmd_scan(self, args):
        print("kk")

        if sys.platform == "linux2":
            bluetooth._checkaddr(address)
            sock = bluetooth._gethcisock(device)
            timeoutms = int(timeout * 1000)
            try:
                name = bluetooth._bt.hci_read_remote_name( sock, address, timeoutms )
            except bluetooth._bt.error, e:
                print e
                logger.debug("Lookup Failed")
                # name lookup failed.  either a timeout, or I/O error
                name = None
            sock.close()
            return name
        elif sys.platform == "win32":
            if not bluetooth.is_valid_address(address):
                raise ValueError("Invalid Bluetooth address")
                
            return bluetooth.bt.lookup_name( address )

        

    # def cmd_say(self, args):
    #   self.speak(' '.join(args))

    # def speak(self, msg):
    #   subprocess.call(['/usr/bin/espeak', msg])

    # def process_message(self, message):
    #   if message.level > 0:
    #       print("Espeak is speaking a message from %s@%s:\n%s:%s" % (message.sender_name,
    #                                                               message.sender_host,
    #                                                               message.header,
    #                                                               message.body))
    #       self.speak(message.header + message.body)

descriptor = {
    'name' : 'proximity',
    'mode' : PluginMode.MANAGED,
    'class' : ProximityPlugin
}
