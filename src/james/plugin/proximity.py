
from bluetooth import *
import sys
import re

from james.plugin import *

class ProximityPlugin(Plugin):

    def __init__(self, core):
        super(ProximityPlugin, self).__init__(core, ProximityPlugin.name)

        self.create_command('bt_scan', self.cmd_scan, 'scan for visible bluetooth devices')
        self.create_command('prx_scan', self.cmd_proximity_check, 'proximity scan')

        self.status = False

    def terminate(self):
        pass

    def cmd_scan(self, args):
        print("Scanning for visible bluetooth devices...")

        nearby_devices = DeviceDiscoverer().discover_devices(lookup_names = True)

        print "found %d devices" % len(nearby_devices)

        for addr, name in nearby_devices:
            print "  %s - %s" % (addr, name)

    def cmd_proximity_check(self, args):
        self.oldstatus = self.status
        self.status = False

        # so mach man es richtig:
        # http://code.google.com/p/pybluez/source/browse/trunk/examples/advanced/inquiry-with-rssi.py?r=12

        for name in self.core.config['proximity']['watch_bt'].keys():
            client_socket=BluetoothSocket( RFCOMM ) # L2CAP

            mac = self.core.config['proximity']['watch_bt'][name]
            print("Scanning for %s (%s)" % (name, mac))

            try:
                client_socket.connect((mac, 3))
                self.status = True
            except bluetooth._bt.error, e:
                print e
                print("Result: %s" % (e[0]))
                errnum = re.search('^\(([:num:]).*$', str(e))
                print errnum
                for t in e:
                    print ("::%s" % (t))
                if e[0] == 112: #Host is not reachable
                    print("Host is away")
                else:
                    print("Host is home")
                    self.status = True

            client_socket.close()

        if self.status != self.oldstatus:
            self.core.proximity_status.set_status_here(self.status)


        # if sys.platform == "linux2":
        #     print(bluetooth)
        #     bluetooth._checkaddr(address)
        #     sock = bluetooth._gethcisock(device)
        #     timeoutms = int(timeout * 1000)
        #     try:
        #         name = bluetooth._bt.hci_read_remote_name( sock, address, timeoutms )
        #     except bluetooth._bt.error, e:
        #         print e
        #         logger.debug("Lookup Failed")
        #         # name lookup failed.  either a timeout, or I/O error
        #         name = None
        #     sock.close()
        #     return name
        # elif sys.platform == "win32":
        #     if not bluetooth.is_valid_address(address):
        #         raise ValueError("Invalid Bluetooth address")
                
        #     return bluetooth.bt.lookup_name( address )

        

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
