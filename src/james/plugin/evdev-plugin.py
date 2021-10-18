
import evdev
import time

from james.plugin import *


class EvdevThread(PluginThread):

    def __init__(self, plugin, evdev_device):
        super(EvdevThread, self).__init__(plugin)

        self.plugin = plugin
        self.evdev_device = evdev.InputDevice(evdev_device)
        self.logger.debug("EVDEV Device: %s" % evdev_device)

    def work(self):
        blocking = 0
        run = 1
        try:
            while run:
                for event in self.evdev_device.read_loop():

                    if not blocking:
                        self.plugin.workerLock.acquire()
                        run = self.plugin.workerRunning
                        self.plugin.workerLock.release()
                        if run:
                            time.sleep(0.5)
                        else:
                            break

                    blocking = 0

                    if event.type == evdev.ecodes.EV_KEY:
                        self.plugin.send_ir_command(event)
                        blocking = 1
                break

        except RuntimeError as e:
            self.logger.warning('EVDEV Plugin could not be loaded. Retrying in 5 seconds. %s' % e)
            time.sleep(5)
            self.work()

    def on_exit(self, result):
        self.logger.info('Exited with (%s)' % result)


class EvdevPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(EvdevPlugin, self).__init__(core, descriptor)

        list_command = self.commands.create_subcommand('list', 'Will return all available evdev devices',
                                                       self.cmd_list_devices)
        list_command.create_subcommand('rcv', 'Will return all watched IR signals', self.cmd_list_rcv)

        self.workerLock = threading.Lock()
        self.workerRunning = True

        for path, name, phys in self.get_all_devices():
            if name == self.config['nodes'][self.core.hostname]['device_name']:
                self.logger.info("Spawning worker for evdev %s" % name)
                self.evdev_worker_thread = EvdevThread(self, path)
                self.evdev_worker_thread.start()
                break

        self.load_state('commandsReceived', 0)

    def get_all_devices(self):
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        devices_return = []
        for device in devices:
            self.logger.debug("Found evdev device: %s - %s - %s" % (device.path, device.name, device.phys))
            devices_return.append((device.path, device.name, device.phys))
        return devices_return

    def send_ir_command(self, event):
        data = evdev.categorize(event)
        self.logger.debug('IR Received keycode request (%s)' % data.keycode)
        for entry in self.config['nodes'][self.core.hostname]['rcvCommands']:
            for lala in entry.keys():
                print(lala)
            name, command = entry.items()
            if name == data.keycode:
                command = self.config['nodes'][self.core.hostname]['rcvCommands'][data.keycode]
                self.logger.info('IR Received command request (%s)' % command)
        self.commandsReceived += 1
        self.core.add_timeout(0, self.send_command, command.split())

    def cmd_list_rcv(self, args):
        ret = []
        try:
            for remote in self.config['nodes'][self.core.hostname]['rcvCommands']:
                for command in self.config['nodes'][self.core.hostname]['rcvCommands'][remote]:
                    for key in list(command.keys()):
                        ret.append('%-15s %-15s %s' % (remote, key, command[key]))
        except TypeError:
            pass
        return ret

    def cmd_list_devices(self, args):
        ret = []
        for path, name, phys in self.get_all_devices():
            ret.append('%-15s %-15s %s' % (path, name, phys))
        return ret

    def terminate(self):
        self.workerLock.acquire()
        self.workerRunning = False
        self.workerLock.release()

    def return_status(self, verbose = False):
        ret = {'commandsReceived': self.commandsReceived}
        return ret


descriptor = {
    'name' : 'evdev-client',
    'help' : 'Interface to EVDEV',
    'command' : 'evdev',
    'mode' : PluginMode.MANAGED,
    'class' : EvdevPlugin,
    'detailsNames' : { 'commandsReceived' : "IR Commands received"}
}
