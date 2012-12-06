
import os
import io
import json
import yaml

class YamlConfig (object):
	def __init__(self, filename = None):
		self.filename = filename
		self.values = {}
		if filename:
			self.load()

	def load(self):
		f = open(self.filename)
		self.values = yaml.safe_load(f)
		f.close()

	def save(self):
		#FIXME: untested!
		f = open(filename, "w")
		yaml.dump(self.values, f)
		f.close()

	def get_values(self):
		return self.values

	def set_values(self, values):
		self.values = values


class JsonConfig (object):
	def __init__(self, filename):
		self.filename = filename
		self.values = {}
		self.load()

	def load(self):
		self.values = json.loads(open(self.filename).read())

	def save(self):
		#FIXME: untested!
		pass
		with io.open(self.filename, 'w', encoding='utf-8') as outfile:
			json.dumps(self.values, outfile)
		pass

	def get_values(self):
		return self.values

	def set_values(self, values):
		self.values = values

