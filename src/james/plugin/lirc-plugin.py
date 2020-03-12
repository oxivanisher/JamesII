# Sources:
# http://alexba.in/blog/2013/01/06/setting-up-lirc-on-the-raspberrypi/
# http://alexba.in/blog/2013/02/23/controlling-lirc-from-the-web/
# http://aron.ws/projects/lirc_rpi/
# https://github.com/slimjim777/web-irsend
# http://pylirc.cvs.sourceforge.net/viewvc/pylirc/pylirc/doc/simple.txt?revision=1.4&view=markup
# https://code.fluendo.com/remotecontrol/trac/browser/trunk/test/test-pylirc.py

import pylirc
import time
import tempfile
import os
from subprocess import call

from james.plugin import *

LIRC_CFG_FILE = '/etc/lirc/lircd.conf'

class LircThread(PluginThread):

    def __init__(self, plugin, rcv_config):
        super(LircThread, self).__init__(plugin)

        self.prog = 'JamesII-lirc'

        self.tempFile = tempfile.NamedTemporaryFile(suffix="-%s" % self.prog, delete=False)
        self.tmpFileName = self.tempFile.name
        self.logger.debug("Tmp File: %s" % self.tmpFileName)
        self.plugin = plugin
        self.tempFile.write(self.create_lircrc(rcv_config))
        self.tempFile.close()

    def work(self):
        blocking = 0
        run = 1
        try:
            if pylirc.init(self.prog, self.tempFile.name):
                while run:

                    if not blocking:
                        self.plugin.workerLock.acquire()
                        run = self.plugin.workerRunning
                        self.plugin.workerLock.release()
                        if run:
                            time.sleep(0.5)
                        else:
                            break

                    s = pylirc.nextcode(1)

                    blocking = 0

                    while s:
                        for code in s:
                            self.plugin.send_ir_command(code["config"])
                        blocking = 1
                        s = []
        except RuntimeError as e:
            self.logger.warning('LIRC Plugin could not be loaded. Retrying in 5 seconds. %s' % e)
            pylirc.exit()
            time.sleep(5)
            self.work()

    def create_lircrc(self, lircrcConfig):
        configReturn = []
        for remote in lircrcConfig.keys():
            for key_dict in lircrcConfig[remote]:
                for key in key_dict.keys():
                    configReturn.append("begin")
                    configReturn.append("\tremote = %s" % remote)
                    configReturn.append("\tbutton = %s" % key)
                    configReturn.append("\tprog   = %s" % self.prog)
                    configReturn.append("\tconfig = %s" % key_dict[key])
                    configReturn.append("end")
        return '\n'.join(configReturn)

    def on_exit(self, result):
        self.logger.info('Exited with (%s)' % result)
        pylirc.exit()
        os.unlink(self.tmpFileName)

class Lirc:
    # THANK YOU! https://github.com/slimjim777/web-irsend/blob/master/lirc/lirc.py
    """
    Parses the lircd.conf file and can send remote commands through irsend.
    """
    codes = {}

    def __init__(self, conf):
        # Open the config file
        self.conf = open(conf, "rb")

        # Parse the config file
        self.parse()
        self.conf.close()

    def devices(self):
        """
        Return a list of devices.
        """
        return self.codes.keys()


    def parse(self):
        """
        Parse the lircd.conf config file and create a dictionary.
        """
        remote_name = None
        code_section = False
        raw_code_section = False

        for line in self.conf:
            # Convert tabs to spaces
            l = line.replace('\t',' ')

            # Look for a 'begin remote' line
            if l.strip()=='begin remote':
                # Got the start of a remote definition
                remote_name = None
                code_section = False

            elif not remote_name and l.strip().find('name')>-1:
                # Got the name of the remote
                remote_name = l.strip().split(' ')[-1]
                if remote_name not in self.codes:
                    self.codes[remote_name] = {}

            elif remote_name and l.strip()=='end remote':
                # Got to the end of a remote definition
                remote_name = None

            elif remote_name and l.strip()=='begin codes':
                code_section = True

            elif remote_name and l.strip()=='end codes':
                code_section = False

            elif remote_name and code_section:
                # Got a code key/value pair... probably
                fields = l.strip().split(' ')
                self.codes[remote_name][fields[0]] = fields[-1]

            elif remote_name and l.strip()=='begin raw_codes':
                raw_code_section = True

            elif remote_name and l.strip()=='end raw_codes':
                raw_code_section = False

            elif remote_name and raw_code_section:
                # Got a raw key code block. Search for name lines...
                fields = l.strip().split(' ')
                if fields[0] == 'name':
                    self.codes[remote_name][fields[1]] = 'raw'


    def send_once(self, device_id, message, count = '1'):
        """
        Send single call to IR LED.
        """
        call(['irsend', 'SEND_ONCE', '--count', count, device_id, message])


class LircPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(LircPlugin, self).__init__(core, descriptor)

        listCommand = self.commands.create_subcommand('list', ('Will list certain things'), None)
        listCommand.create_subcommand('send', ('Will return all sendable commands'), self.cmd_list_send)
        listCommand.create_subcommand('rcv', ('Will return all watched IR signals'), self.cmd_list_rcv)
        listCommand.create_subcommand('devices', ('Will return all available devices (remotes)'), self.cmd_list_devices)

        self.commands.create_subcommand('send', ('Sends a IR signal. Syntax: lirc send remotename keyname'), self.cmd_send)

        self.logger.debug('Loading lircd config from %s' % LIRC_CFG_FILE)
        if os.path.exists(LIRC_CFG_FILE):
            self.lircParse = Lirc(LIRC_CFG_FILE)

            self.workerLock = threading.Lock()
            self.workerRunning = True

            self.lirc_thread = LircThread(self, self.config['nodes'][self.core.hostname]['rcvCommands'])
            self.lirc_thread.start()

        else:
            self.logger.warning('LIRC_CFG_FILE (%s) not found. Plugin will not work!' % LIRC_CFG_FILE)
            self.workerRunning = False

        self.load_state('commandsReceived', 0)
        self.load_state('commandsSent', 0)

    def send_ir_command(self, command):
        self.logger.info('IR Received command request (%s)' % command)
        self.commandsReceived += 1
        self.core.add_timeout(0, self.send_command, command.split())

    def cmd_send(self, args):
        try:
            count = args[2]
        except Exception:
            count = '1'

        try:
            if args[1] in self.config['nodes'][self.core.hostname]['sendCommands'][args[0]]:
                self.lircParse.send_once(args[0], args[1], count)
                self.logger.info('IR Send Remote: %s Command: %s Count: %s' % (args[0], args[1], count))
                self.commandsSent += 1
                return 'IR Send Remote: %s Command: %s Count: %s' % (args[0], args[1], count)
        except Exception:
            pass

        self.logger.warning('Unknown IR Remote/Command: (%s)' % (' '.join(args)))
        return 'Unknown IR Remote/Command: (%s)' % (' '.join(args))


    def cmd_list_send(self, args):
        ret = []
        try:
            for remote in self.config['nodes'][self.core.hostname]['sendCommands']:
                for command in self.config['nodes'][self.core.hostname]['sendCommands'][remote]:
                    ret.append('%-15s %s' % (remote, command))
        except TypeError:
            pass
        return ret

    def cmd_list_rcv(self, args):
        ret = []
        try:
            for remote in self.config['nodes'][self.core.hostname]['rcvCommands']:
                for command in self.config['nodes'][self.core.hostname]['rcvCommands'][remote]:
                    for key in command.keys():
                        ret.append('%-15s %-15s %s' % (remote, key, command[key]))
        except TypeError:
            pass
        return ret

    def cmd_list_devices(self, args):
        ret = []
        for dev in self.lircParse.codes:
            for code in self.lircParse.codes[dev]:
                ret.append('%-15s %-15s %s' % (dev, code, self.lircParse.codes[dev][code]))
        return ret


    def terminate(self):
        self.workerLock.acquire()
        self.workerRunning = False
        self.workerLock.release()

    def return_status(self, verbose = False):
        ret = {}
        ret['commandsSent'] = self.commandsSent
        ret['commandsReceived'] = self.commandsReceived
        return ret

    # react on proximity events
    def process_proximity_event(self, newstatus):
        if (time.time() - self.core.startup_timestamp) > 10:
            self.logger.debug("LIRC processing proximity event")
            try:
                for entry in self.config['nodes'][self.core.hostname]['proximityToggle']:
                    for command in entry.keys():
                        self.core.add_timeout(0, self.cmd_send, [command, entry[command]])
            except TypeError:
                pass
            if newstatus['status'][self.core.location]:
                try:
                    for entry in self.config['nodes'][self.core.hostname]['proximityHome']:
                        for command in entry.keys():
                            self.core.add_timeout(0, self.cmd_send, [command, entry[command]])
                except TypeError:
                    pass
            else:
                try:
                    for entry in self.config['nodes'][self.core.hostname]['proximityGone']:
                        for command in entry.keys():
                            self.core.add_timeout(0, self.cmd_send, [command, entry[command]])
                except TypeError:
                    pass
        return True

descriptor = {
    'name' : 'lirc-client',
    'help' : 'Interface to LIRC',
    'command' : 'lirc',
    'mode' : PluginMode.MANAGED,
    'class' : LircPlugin,
    'detailsNames' : { 'commandsSent' : "IR Commands sent",
                       'commandsReceived' : "IR Commands received"}
}
