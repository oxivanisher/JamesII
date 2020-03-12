import smbus

from james.plugin import *


class RGBLEDPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(RGBLEDPlugin, self).__init__(core, descriptor)

        self.commands.create_subcommand('sunrise', 'Start a sunrise', self.cmd_sunrise)
        self.commands.create_subcommand('color', 'Set the color', self.cmd_color)
        self.commands.create_subcommand('fade', 'Fade to color', self.cmd_fade)
        self.commands.create_subcommand('rainbow', 'Show rainbow', self.cmd_rainbow)
        self.commands.create_subcommand('fire', 'Show fire', self.cmd_fire)
        self.commands.create_subcommand('off', 'Switch LEDs off', self.cmd_off)

        self.load_state('sunrises', 0)

        self.bus = smbus.SMBus(1)
        self.address = 0x04

    def send_over_i2c(self, what, arguments=[0]):
        self.logger.info("Sending command %s over i2c with args: %s" % (what, arguments))
        try:
            self.bus.write_i2c_block_data(self.address, what, [int(i) for i in arguments])
        except IOError as e:
            self.logger.info("send_over_i2c encountered a IOError: %s" % (str(e)))

    def cmd_sunrise(self, args):
        if self.core.proximity_status.get_status_here():
            self.sunrise()
            return ["Sunrise enabled"]
        else:
            msg="Sunrise not activated. You are not here."
            self.logger.info(msg)
            return [msg]

    def cmd_color(self, args):
        if self.core.proximity_status.get_status_here():
            self.color(args)
            return ["Fixed color set to %s" % ', '.join(args)]
        else:
            msg="Fixed color not activated. You are not here."
            self.logger.info(msg)
            return [msg]

    def cmd_fade(self, args):
        if self.core.proximity_status.get_status_here():
            self.fade(args)
            return ["Fade to color %s" % ', '.join(args)]
        else:
            msg="Fade to color not activated. You are not here."
            self.logger.info(msg)
            return [msg]

    def cmd_rainbow(self, args):
        if self.core.proximity_status.get_status_here():
            self.rainbow(args)
            return ["Show rainbow colors"]
        else:
            msg="Rainbow not activated. You are not here."
            self.logger.info(msg)
            return [msg]

    def cmd_fire(self, args):
        if self.core.proximity_status.get_status_here():
            self.fire(args)
            return ["Show fire"]
        else:
            msg="Fire not activated. You are not here."
            self.logger.info(msg)
            return [msg]

    def cmd_off(self, args):
        self.off(args)
        return ["LEDs switched off"]

    def sunrise(self):
        self.sunrises += 1
        self.send_over_i2c(1)

    def color(self, args):
        self.send_over_i2c(2, args)

    def fade(self, args):
        self.send_over_i2c(3, args)

    def rainbow(self, args):
        self.send_over_i2c(4)

    def fire(self, args):
        self.send_over_i2c(5)

    def off(self, args):
        self.send_over_i2c(0)

    # react on proximity events
    def process_proximity_event(self, newstatus):
        if (time.time() - self.core.startup_timestamp) > 10:
            self.logger.debug("RGB-LED Processing proximity event")
            if newstatus['status'][self.core.location]:
                # If automatic RGB LED on coming home should be implemented, this is the place for it
                # See the MPD Client for details.
                pass
            else:
                self.core.add_timeout(0, self.off, False)

    def return_status(self, verbose=False):
        self.logger.debug('Showing status')
        return {'sunrises': self.sunrises}


descriptor = {
    'name': 'rgb-led',
    'help': 'Interface to RGB LEDs over a arduino attached to I2C',
    'command': 'rgb',
    'mode': PluginMode.MANAGED,
    'class': RGBLEDPlugin,
    'detailsNames': {'sunrises': "Sunrises"}
}
