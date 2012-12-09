
class LogLevel(object):
	DEBUG = 0
	INFO = 1
	WARN = 2
	ERROR = 3


class Logger(object):

	def __init__(self):
		self.level = LogLevel.DEBUG

	def set_level(self, level):
		self.level = level

	def debug(self, str):
		self.log(LogLevel.DEBUG, str)
		pass

	def info(self, str):
		pass

	def warn(self, str):
		pass

	def error(self, str):
		pass

	def log(self, level, str):
		if level >= self.level:
			self.output(str)

	def output(self, str):
		print output



# local = Logger()