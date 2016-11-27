
import smbus

from james.plugin import *


class RGBLEDPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(RGBLEDPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('sunrise', 'Start a sunrise', self.cmd_sunrise)
        self.commands.create_subcommand('color', 'Set the color', self.cmd_color)
        self.commands.create_subcommand('off', 'Switch LEDs off', self.cmd_off)

        self.load_state('sunrises', 0)

        self.bus = smbus.SMBus(1)
        self.address = 0x04

    def send_data(self, command, args = 0):
        self.bus.write_i2c_block_data(self.address, chr(command), [chr(i) for i in args])

    def cmd_sunrise(self, args):
        self.sunrise()
        return (["Sunrise enabled"])

    def cmd_color(self, args):
        self.color(args)
        return (["Fixed color set to %s" % ', '.join(args)])

    def cmd_off(self, args):
        self.off()
        return (["LEDs switched off"])

    def sunrise(self):
        self.sunrises += 1
        self.send_data(self, 1)

    def color(self, args):
        self.send_data(self, 2, args)

    def off(self):
        self.send_data(self, 0)

    def return_status(self):
        self.logger.debug('Showing status')
        ret = {}
        ret['sunrises'] = self.sunrises
        return ret

descriptor = {
    'name' : 'rgb-led',
    'help' : 'Interface to RGB LEDs over a arduino attached to I2C',
    'command' : 'rgb',
    'mode' : PluginMode.MANAGED,
    'class' : RGBLEDPlugin,
    'detailsNames' : { 'sunrises' : "Sunrises" }
}
