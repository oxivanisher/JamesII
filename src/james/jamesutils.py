
import time
#from datetime import datetime
import datetime
import pytz

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
		timezone = pytz.timezone(self.core.config.values['core']['timezone'])

		now = datetime.datetime.now(timezone)
		event = datetime.datetime.fromtimestamp(timestamp, timezone)
		event_timestamp = int(event.strftime('%s'))
		midnight_timestamp = int(timezone.localize(now.replace(hour=0, minute=0, second=0, microsecond=0,
															tzinfo=None), is_dst=None).strftime('%s'))
		newyear_timestamp = int(timezone.localize(now.replace(day=1, month=1, hour=0, minute=0, second=0,
															microsecond=0, tzinfo=None), is_dst=None).strftime('%s'))
		if age == 0:
			return 'infinite'
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
