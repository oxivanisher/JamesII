import threading

import evdev
import time

from james.plugin import *


class EvdevThread(PluginThread):

    def __init__(self, plugin, evdev_path, evdev_name):
        super(EvdevThread, self).__init__(plugin)

        self.device_name = evdev_name
        self.evdev_device = evdev.InputDevice(evdev_path)
        self.logger.debug("EVDEV Device: %s" % evdev_path)
        self.name = "%s > Device: %s - %s" % (self.name, evdev_name, evdev_path)
        self.callback_timeout = time.time() + 2

    def work(self):
        # blocking = 0
        run = 1
        try:
            while run:
                event = self.evdev_device.read_one()
                if event:
                    if event.type == evdev.ecodes.EV_KEY:
                        self.plugin.workerLock.acquire()
                        self.plugin.received_button(self.device_name, event)
                        self.plugin.workerLock.release()

                # only check every 2 seconds to make evdev react faster
                if self.callback_timeout < time.time():
                    self.plugin.workerLock.acquire()
                    run = self.plugin.workerRunning
                    self.plugin.workerLock.release()
                    self.callback_timeout = time.time() + 2

                if run:
                    time.sleep(0.05)
                else:
                    break

        except RuntimeError as e:
            self.logger.warning('EVDEV Plugin could not be loaded. Retrying in 5 seconds. %s' % e)
            time.sleep(5)
            self.work()

    def on_exit(self, result=0):
        self.logger.info('Exited with (%s)' % result)


class EvdevPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(EvdevPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('devices', 'Will return all available evdev devices', self.cmd_list_devices)
        self.commands.create_subcommand('buttons', 'Will return all configured buttons', self.cmd_list_buttons)

        self.workerLock = threading.Lock()
        self.commandsReceived = 0
        self.workerRunning = True

        for name, path, phys in self.get_all_devices():
            for device_name in self.config['nodes'][self.core.hostname]:
                if name == device_name:
                    evdev_worker_thread = EvdevThread(self, path, name)
                    evdev_worker_thread.start()
                    self.logger.info(f"Spawned worker for evdev {name} on path {path} with PID {evdev_worker_thread.native_id}")
                    self.worker_threads.append(evdev_worker_thread)

        self.load_state('commandsReceived', 0)

    def get_all_devices(self):
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        devices_return = []
        for device in devices:
            self.logger.debug("Found evdev device: %s - %s - %s" % (device.name, device.path, device.phys))
            devices_return.append((device.name, device.path, device.phys))
        return devices_return

    def received_button(self, device_name, event):
        data = evdev.categorize(event)
        value = event.value
        self.logger.debug('Button press request: Device: %s; Keycode: %s; Value: %s)' %
                          (device_name, data.keycode, value))
        # value 1: key down, value 0: key up
        if value:
            for button in self.config['nodes'][self.core.hostname][device_name].keys():
                if button == data.keycode:
                    command = self.config['nodes'][self.core.hostname][device_name][button]
                    self.logger.info('Evdev button command (%s)' % command)
                    self.commandsReceived += 1
                    self.core.add_timeout(0, self.send_command, command.split())

    def cmd_list_buttons(self, args):
        ret = []
        try:
            for device_name in sorted(self.config['nodes'][self.core.hostname]):
                for button in sorted(self.config['nodes'][self.core.hostname][device_name].keys()):
                    command = self.config['nodes'][self.core.hostname][device_name][button]
                    ret.append('%-15s %-15s %s' % (device_name, button, command))
        except TypeError:
            pass
        return ret

    def cmd_list_devices(self, args):
        ret = []
        for name, path, phys in self.get_all_devices():
            ret.append('%-25s %-15s %s' % (name, path, phys))
        return ret

    def terminate(self):
        self.logger.info('Signalling the device workers to exit')
        self.workerLock.acquire()
        self.workerRunning = False
        self.workerLock.release()
        # self.wait_for_threads()

    def return_status(self, verbose=False):
        ret = {'commandsReceived': self.commandsReceived}
        return ret


descriptor = {
    'name': 'evdev-client',
    'help_text': 'Interface to EVDEV',
    'command': 'evdev',
    'mode': PluginMode.MANAGED,
    'class': EvdevPlugin,
    'detailsNames': {'commandsReceived': "Button presses received"}
}
