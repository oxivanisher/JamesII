
import time
import datetime
import pytz
import socket
import struct
import collections
import subprocess

class JamesUtils(object):

    def __init__(self, core):
        self.core = core

    def get_short_age(self, timestamp):
        age = int(time.time() - timestamp)
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

        fmt = '%Y-%m-%d %H:%M:%S %Z%z'
        timezone = pytz.timezone(self.core.config['core']['timezone'])

        now = datetime.datetime.now(timezone)
        event = datetime.datetime.fromtimestamp(timestamp, timezone)
        event_timestamp = int(event.strftime('%s'))
        midnight_timestamp = int(timezone.localize(now.replace(hour=0, minute=0, second=0, microsecond=0,
                                                               tzinfo=None), is_dst=None).strftime('%s'))
        newyear_timestamp = int(timezone.localize(now.replace(day=1, month=1, hour=0, minute=0, second=0,
                                                              microsecond=0, tzinfo=None), is_dst=None).strftime('%s'))
        if age == 0:
            return 'just now'
        elif age < 60:
            return '%s seconds ago' % (age)
        elif age < 3600:
            return '%s minutes ago' % (int(age / 60))
        elif event_timestamp > midnight_timestamp:
            return 'today at %s:%s' % (event.strftime('%H'), event.strftime('%M'))
        elif event_timestamp > (midnight_timestamp - 86400):
            return 'yesterday at %s:%s' % (event.strftime('%H'), event.strftime('%M'))
        elif age <= 604800:
            return event.strftime('last %A')
        elif event_timestamp > newyear_timestamp:
            return event.strftime('at the %d. of %B')
        else:
            return event.strftime('at the %d. of %b. %Y')

    def bytes2human(self, n):
        # http://code.activestate.com/recipes/578019
        symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
        prefix = {}
        for i, s in enumerate(symbols):
            prefix[s] = 1 << (i+1)*10
        for s in reversed(symbols):
            if n >= prefix[s]:
                value = float(n) / prefix[s]
                return '%.1f%s' % (value, s)
        return "%sB" % n

    def wake_on_lan(self, macaddress):
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
        if isinstance(data, unicode):
            return str(data)
        elif isinstance(data, collections.Mapping):
            return dict(map(self.convert_from_unicode, data.iteritems()))
        elif isinstance(data, collections.Iterable):
            return type(data)(map(self.convert_from_unicode, data))
        else:
            return data

    def list_unicode_cleanup(Self, data):
        args = [s.encode('utf-8', 'ignore').strip() for s in data]
        args = filter(lambda s: s != '', args)
        return args

    def popenAndWait(self, command):
        """
        Runs the given command in a subprocess but will not spawn a subprocess.
        """
        ret = subprocess.Popen(command, \
                  stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]
        return ret.split("\n")
