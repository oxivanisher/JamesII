import time
import datetime
import pytz
import socket
import struct
from collections.abc import Mapping, Iterable
import subprocess
import logging
import re


class JamesUtils(object):

    def __init__(self, core):
        self.core = core
        self.list_unicode_cleanup_tmp = []

    def get_short_age(self, timestamp):
        age = int(time.time() - timestamp)

        if age < 0:
            age = age * -1

        if age == 0:
            return ''
        elif age < 60:
            return '%ss' % age
        elif 59 < age < 3600:
            return '%sm' % (int(age / 60))
        elif 3600 <= age < 86400:
            return '%sh' % (int(age / 3600))
        elif 86400 <= age < 604800:
            return '%sd' % (int(age / 86400))
        elif 604800 <= age < 31449600:
            return '%sw' % (int(age / 604800))
        else:
            return '%sy' % (int(age / 31449600))

    def get_nice_age(self, timestamp):
        age = int(time.time() - timestamp)
        in_time = int(timestamp - time.time())

        fmt = '%Y-%m-%d %H:%M:%S %Z%z'
        timezone = pytz.timezone(self.core.config['core']['timezone'])

        now = datetime.datetime.now(timezone)
        now_timestamp = int(now.strftime('%s'))
        event = datetime.datetime.fromtimestamp(timestamp, timezone)
        event_timestamp = int(event.strftime('%s'))
        last_midnight_timestamp = int(timezone.localize(now.replace(hour=0, minute=0, second=0, microsecond=0,
                                                                    tzinfo=None), is_dst=None).strftime('%s'))
        next_midnight_timestamp = last_midnight_timestamp + 86400
        past_newyear_timestamp = int(timezone.localize(now.replace(day=1, month=1, hour=0, minute=0, second=0,
                                                                   microsecond=0, tzinfo=None), is_dst=None).strftime(
            '%s'))
        future_newyear_timestamp = int(timezone.localize(now.replace(day=31, month=12, hour=23, minute=59, second=59,
                                                                     microsecond=0, tzinfo=None), is_dst=None).strftime(
            '%s'))
        if age == 0:
            return 'just now'

        # FIXME 2 if blocks for the future and the past
        elif 60 > age >= 0:
            if age == 1:
                return '%s second ago' % age
            else:
                return '%s seconds ago' % age
        elif 3600 > age >= 0:
            if (int(age / 60)) == 1:
                return '%s minute ago' % (int(age / 60))
            else:
                return '%s minutes ago' % (int(age / 60))
        elif 60 > in_time >= 0:
            if in_time == 1:
                return 'in %s second' % in_time
            else:
                return 'in %s seconds' % in_time
        elif 3600 > in_time >= 0:
            if int(in_time / 60) == 1:
                minute_str = 'minute'
            else:
                minute_str = 'minutes'

            if int(in_time % 60) == 1:
                second_str = 'second'
            else:
                second_str = 'seconds'

            return 'in %s %s and %s %s' % (int(in_time / 60), minute_str, int(in_time % 60), second_str)

        elif last_midnight_timestamp < event_timestamp < (last_midnight_timestamp + 86400):
            return 'today at %s:%s:%s' % (event.strftime('%H'),
                                          event.strftime('%M'),
                                          event.strftime('%S'))
        elif (last_midnight_timestamp - 86400) < event_timestamp < now_timestamp:
            return 'yesterday at %s:%s:%s' % (event.strftime('%H'),
                                              event.strftime('%M'),
                                              event.strftime('%S'))
        elif 604800 >= age >= 0:
            return event.strftime('last %A')
        elif past_newyear_timestamp < event_timestamp < now_timestamp:
            return event.strftime('this year at %A the %d of %B at %H:%M:%S')
        elif next_midnight_timestamp <= event_timestamp < (next_midnight_timestamp + 86400):
            return 'tomorrow at %s:%s:%s' % (event.strftime('%H'),
                                             event.strftime('%M'),
                                             event.strftime('%S'))
        elif 604800 >= in_time >= 0:
            return event.strftime('next %A at %H:%M:%S')
        elif future_newyear_timestamp < event_timestamp < (
                future_newyear_timestamp + 31556952):  # NOT leap year save!
            return event.strftime('next year on %A the %d of %B at %H:%M:%S')

        else:
            return event.strftime('at %A the %d %B %Y')

    def duration_string2seconds(self, args):
        wait_seconds = 0

        time_to_strings = [(1, ['second', 'seconds']), (60, ['minute', 'minutes']), (3600, ['hour', 'hours']),
                           (86400, ['day', 'days']), (604800, ['week', 'weeks'])]
        for (multiplier, strings) in time_to_strings:
            for string in strings:
                if string in args:
                    index = args.index(string)
                    if index > 0:
                        try:
                            count = int(args[index - 1])
                            if count > 0:
                                wait_seconds += multiplier * count
                                args.pop(index)
                                args.pop(index - 1)
                        except Exception as e:
                            pass

        try:
            wait_seconds += int(args[0])
            args.pop(0)
        except IndexError:
            return False
        except ValueError:
            wait_seconds_start = wait_seconds
            matched = re.findall(r'(\d+)([smhdw])', args[0])
            for (digit, multiplier_id) in matched:
                if multiplier_id == 's':
                    wait_seconds += int(digit)
                elif multiplier_id == 'm':
                    wait_seconds += int(digit) * 60
                elif multiplier_id == 'h':
                    wait_seconds += int(digit) * 3600
                elif multiplier_id == 'd':
                    wait_seconds += int(digit) * 86400
                elif multiplier_id == 'w':
                    wait_seconds += int(digit) * 604800
                else:
                    found = False

            if wait_seconds_start != wait_seconds:
                args.pop(0)

        return wait_seconds, args

    def time_string2seconds(self, arg):
        # converts 12:22 and 12:22:33 into seconds
        seconds = 0
        minutes = 0
        hours = 0
        try:
            if arg.count(':') == 2:
                data = arg.split(':')
                seconds = int(data[2])
                minutes = int(data[1])
                hours = int(data[0])
            elif arg.count(':') == 1:
                data = arg.split(':')
                minutes = int(data[1])
                hours = int(data[0])
        except Exception as e:
            pass
        return hours * 3600 + minutes * 60 + int(seconds)

    def date_string2values(self, arg):
        # converts yyyy-mm-dd into [yyyy, mm, dd]
        try:
            data = arg.split('-')
            if int(data[0]) > 2020:
                if 0 < int(data[1]) < 13:
                    if 0 < int(data[2]) < 32:
                        return [int(data[0]), int(data[1]), int(data[2])]
        except Exception as e:
            return False

    def get_time_string(self):
        now = datetime.datetime.now()

        return "%s:%02d" % (now.hour, now.minute)

    def bytes2human(self, n):
        # http://code.activestate.com/recipes/578019
        symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
        prefix = {}
        for i, s in enumerate(symbols):
            prefix[s] = 1 << (i + 1) * 10
        for s in reversed(symbols):
            if n >= prefix[s]:
                value = float(n) / prefix[s]
                return '%.1f%s' % (value, s)
        return "%sB" % n

    def wake_on_lan(self, macaddress):
        logger = self.get_logger('jamesutils', self.core.logger)
        logger.debug('Wake on lan called for (%s)' % macaddress)
        # http://code.activestate.com/recipes/358449-wake-on-lan/
        """ Switches on remote computers using WOL. """

        def send_magic_packet(mac_address):
            # Create a UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            # Construct the magic packet
            mac_bytes = bytes.fromhex(mac_address)
            magic_packet = b'\xff' * 6 + mac_bytes * 16

            # Send the magic packet
            sock.sendto(magic_packet, ('<broadcast>', 9))

            # Close the socket
            sock.close()

        # Check macaddress format and try to compensate.
        if len(macaddress) == 12:
            pass
        elif len(macaddress) == 12 + 5:
            sep = macaddress[2]
            macaddress = macaddress.replace(sep, '')
        else:
            raise ValueError('Incorrect MAC address format')

        send_magic_packet(macaddress)

    def convert_from_unicode(self, data):
        if isinstance(data, str):
            return str(data)
        elif isinstance(data, Mapping):
            return dict(list(map(self.convert_from_unicode, iter(data.items()))))
        elif isinstance(data, Iterable):
            return type(data)(list(map(self.convert_from_unicode, data)))
        else:
            return data

    def list_unicode_cleanup(self, data):
        try:
            args = [s.strip() for s in data]
        except UnicodeDecodeError as e:
            if self.list_unicode_cleanup_tmp != data:
                logger = self.get_logger('jamesutils')
                logger.warning("Error in list_unicode_cleanup, not unicode cleared: %s" % data)
                self.list_unicode_cleanup_tmp = data
            args = data

        args = [s for s in args if s != '']
        return args

    def popen_and_wait(self, command):
        """
        Runs the given command in a subprocess but will not spawn a subprocess.
        """
        logger = self.get_logger('jamesutils', self.core.logger)
        logger.debug('popenAndWait: %s' % command)
        ret = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]
        return ret.decode('UTF-8').split("\n")

    def get_logger(self, name, parent=None):

        if parent:
            return parent.getChild(name)
        else:
            # %(module)s
            file_formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s: %(msg)s')
            screen_formatter = ShortNameFormatter('%(asctime)s %(levelname)-8s %(shortname)s: %(msg)s')

            log = logging.getLogger(name)
            log.setLevel(logging.INFO)

            # screen handler
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.DEBUG)
            stream_handler.setFormatter(screen_formatter)
            log.addHandler(stream_handler)

            # file handler
            try:
                filehandler = logging.FileHandler("./JamesII.log")
                filehandler.setLevel(logging.DEBUG)
                filehandler.setFormatter(file_formatter)
                log.addHandler(filehandler)
            except Exception:
                log.warning("WARNING: Unable to open Logfile for writing")
                pass

            return log

    def dict_deep_compare(self, dict1, dict2):
        """
        Performs a deep comparison of two dictionaries.

        Args:
            dict1 (dict): The first dictionary to compare.
            dict2 (dict): The second dictionary to compare.

        Returns:
            bool: True if the dictionaries are equal, False otherwise.
        """
        if isinstance(dict1, dict) and isinstance(dict2, dict):
            if len(dict1) != len(dict2):
                return False
            for key in dict1:
                if key not in dict2:
                    return False
                if not self.dict_deep_compare(dict1[key], dict2[key]):
                    return False
            return True
        else:
            return dict1 == dict2

class ShortNameFormatter(logging.Formatter):
    def format(self, record):
        # keep only the last component of the logger name
        short_name_list = record.name.split('.')[2:]
        if len(short_name_list):
            record.shortname = '.'.join(short_name_list)
        else:
            record.shortname = 'core'
        return super().format(record)

# http://programmersought.com/article/25261763501/;jsessionid=DFBA728A86933CC02C3CE05B8353610C
# https://stackoverflow.com/questions/39146039/pickle-typeerror-a-bytes-like-object-is-required-not-str
class StrToBytes:
    def __init__(self, file_object):
        self.file_object = file_object

    def read(self, size):
        # return self.file_object.read(size).encode()
        return self.file_object.read(size)

    def readline(self, size=-1):
        # return self.file_object.readline(size).encode()
        return self.file_object.readline(size)


def cmp(a, b):
    return (a > b) - (a < b)
