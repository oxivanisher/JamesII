import time
import datetime
import pytz
import socket
import struct
import collections
import subprocess
import logging
import re


class JamesUtils(object):

    def __init__(self, core):
        self.core = core
        self.listUnicodeCleanuptmp = []

    def get_short_age(self, timestamp):
        age = int(time.time() - timestamp)

        if age < 0:
            age = age * -1

        if age == 0:
            return ''
        elif age < 60:
            return '%ss' % (age)
        elif age > 59 and age < 3600:
            return '%sm' % (int(age / 60))
        elif age >= 3600 and age < 86400:
            return '%sh' % (int(age / 3600))
        elif age >= 86400 and age < 604800:
            return '%sd' % (int(age / 86400))
        elif age >= 604800 and age < 31449600:
            return '%sw' % (int(age / 604800))
        else:
            return '%sy' % (int(age / 31449600))

    def get_nice_age(self, timestamp):
        age = int(time.time() - timestamp)
        intime = int(timestamp - time.time())

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

        # FIXME 2 if bloecke fuer zukunft und vergangenheit
        elif age < 60 and age >= 0:
            if age == 1:
                return '%s second ago' % (age)
            else:
                return '%s seconds ago' % (age)
        elif age < 3600 and age >= 0:
            if (int(age / 60)) == 1:
                return '%s minute ago' % (int(age / 60))
            else:
                return '%s minutes ago' % (int(age / 60))
        elif intime < 60 and intime >= 0:
            if intime == 1:
                return 'in %s second' % (intime)
            else:
                return 'in %s seconds' % (intime)
        elif intime < 3600 and intime >= 0:
            if int(intime / 60) == 1:
                minute_str = 'minute'
            else:
                minute_str = 'minutes'

            if int(intime % 60) == 1:
                second_str = 'second'
            else:
                second_str = 'seconds'

            return 'in %s %s and %s %s' % (int(intime / 60), minute_str, int(intime % 60), second_str)

        elif event_timestamp > last_midnight_timestamp and event_timestamp < (last_midnight_timestamp + 86400):
            return 'today at %s:%s:%s' % (event.strftime('%H'),
                                          event.strftime('%M'),
                                          event.strftime('%S'))
        elif event_timestamp > (last_midnight_timestamp - 86400) and event_timestamp < now_timestamp:
            return 'yesterday at %s:%s:%s' % (event.strftime('%H'),
                                              event.strftime('%M'),
                                              event.strftime('%S'))
        elif age <= 604800 and age >= 0:
            return event.strftime('last %A')
        elif event_timestamp > past_newyear_timestamp and event_timestamp < now_timestamp:
            return event.strftime('this year at %A the %d of %B at %H:%M:%S')
        elif event_timestamp >= next_midnight_timestamp and event_timestamp < (next_midnight_timestamp + 86400):
            return 'tomorrow at %s:%s:%s' % (event.strftime('%H'),
                                             event.strftime('%M'),
                                             event.strftime('%S'))
        elif intime <= 604800 and intime >= 0:
            return event.strftime('next %A at %H:%M:%S')
        elif event_timestamp > future_newyear_timestamp and event_timestamp < (
                future_newyear_timestamp + 31556952):  # NOT leap year save!
            return event.strftime('next year on %A the %d of %B at %H:%M:%S')

        else:
            return event.strftime('at %A the %d %B %Y')

    def duration_string2seconds(self, args):
        wait_seconds = 0

        timeToStrings = []
        timeToStrings.append((1, ['second', 'seconds']))
        timeToStrings.append((60, ['minute', 'minutes']))
        timeToStrings.append((3600, ['hour', 'hours']))
        timeToStrings.append((86400, ['day', 'days']))
        timeToStrings.append((604800, ['week', 'weeks']))
        for (multiplier, strings) in timeToStrings:
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
            wait_secondsStart = wait_seconds
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

            if wait_secondsStart != wait_seconds:
                args.pop(0)

        return (wait_seconds, args)

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
        return (hours * 3600 + minutes * 60 + int(seconds))

    def date_string2values(self, arg):
        # converts dd-mm-yyyy into [yyyy, mm, dd]
        try:
            data = arg.split('-')
            if int(data[0]) > 0 and int(data[0]) < 13:
                if int(data[1]) > 0 and int(data[1]) < 32:
                    if int(data[2]) > 2012:
                        return [int(data[2]), int(data[1]), int(data[0])]
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
        logger = self.getLogger('jamesutils', self.core.logger)
        logger.debug('Wake on lan called for (%s)' % macaddress)
        # http://code.activestate.com/recipes/358449-wake-on-lan/
        """ Switches on remote computers using WOL. """

        # Check macaddress format and try to compensate.
        if len(macaddress) == 12:
            pass
        elif len(macaddress) == 12 + 5:
            sep = macaddress[2]
            macaddress = macaddress.replace(sep, '')
        else:
            raise ValueError('Incorrect MAC address format')

        # Pad the synchronization stream.
        data = ''.join(['FFFFFFFFFFFF', macaddress * 20])
        send_data = ''

        # Split up the hex values and pack.
        for i in range(0, len(data), 2):
            send_data = ''.join([send_data,
                                 struct.pack('B', int(data[i: i + 2], 16))])

        # Broadcast it to the LAN.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(send_data, ('<broadcast>', 7))

    def convert_from_unicode(self, data):
        if isinstance(data, str):
            return str(data)
        elif isinstance(data, collections.Mapping):
            return dict(list(map(self.convert_from_unicode, iter(data.items()))))
        elif isinstance(data, collections.Iterable):
            return type(data)(list(map(self.convert_from_unicode, data)))
        else:
            return data

    def list_unicode_cleanup(self, data):
        try:
            args = [s.encode('utf-8', errors='ignore').strip() for s in data]
        except UnicodeDecodeError as e:
            if self.listUnicodeCleanuptmp != data:
                logger = self.getLogger('jamesutils')
                logger.warning("Error in list_unicode_cleanup, not unicode cleared: %s" % data)
                self.listUnicodeCleanuptmp = data
            args = data

        args = [s for s in args if s != '']
        return args

    def popenAndWait(self, command):
        """
        Runs the given command in a subprocess but will not spawn a subprocess.
        """
        logger = self.getLogger('jamesutils', self.core.logger)
        logger.debug('popenAndWait: %s' % command)
        ret = subprocess.Popen(command, \
                               stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]
        return ret.split("\n")

    def getLogger(self, name, parent=None):

        if parent:
            return parent.getChild(name)
        else:
            # %(module)s
            file_formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s: %(message)s')
            screen_formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')

            log = logging.getLogger(name)
            log.setLevel(logging.INFO)

            # screen handler
            streamhandler = logging.StreamHandler()
            streamhandler.setLevel(logging.DEBUG)
            streamhandler.setFormatter(screen_formatter)
            log.addHandler(streamhandler)

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


# http://programmersought.com/article/25261763501/;jsessionid=DFBA728A86933CC02C3CE05B8353610C
class StrToBytes:
    def __init__(self, fileobj):
        self.fileobj = fileobj

    def read(self, size):
        return self.fileobj.read(size).encode()

    def readline(self, size=-1):
        return self.fileobj.readline(size).encode()
