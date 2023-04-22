import json
import yaml


class YamlConfig (object):
    def __init__(self, filename=None):
        self.filename = filename
        self.values = {}
        if filename:
            self.load()

    def load(self):
        f = open(self.filename)
        self.values = yaml.safe_load(f)
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

    def get_values(self):
        return self.values

    def set_values(self, values):
        self.values = values

