
import time

class JamesUtils(object):
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
		if age == 0:
			return 'never'
		elif age < 60:
			return 'before %s seconds' % (age)
		elif age < 3600:
			return 'before %s minutes' % (int(age / 60))
#		elif age > http://stackoverflow.com/questions/373370/how-do-i-get-the-utc-time-of-midnight-for-a-given-timezone
#         } elseif ($timestamp > strtotime(date('n') . '/' . date('j') . '/' . date('Y'))) {
#             $ageOfMsgReturn = strftime("Heute um %H:%M Uhr", $timestamp);
#         } elseif ($timestamp > strtotime(date('m/d/y', mktime(0, 0, 0, date("m"), date("d") - 1, date("Y"))))) {
#             $ageOfMsgReturn = strftime("Gestern um %H:%M Uhr", $timestamp)
#		elif age <= 604800:
#			return ''
#         } elseif ($ageOfMsg <= '604800') {
#             $ageOfMsgReturn = strftime("Letzten %A", $timestamp);
#         } elseif ($timestamp > strtotime('1/1/' . date('Y'))) {
#             $ageOfMsgReturn = strftime("Am %d. %B", $timestamp);
#         } else {
#             $ageOfMsgReturn = strftime("Am %d. %b. %Y", $timestamp);
		else:
			return str(timestamp)
