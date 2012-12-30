
import sys
import requests
import json

from james.plugin import *

# http://isbullsh.it/2012/06/Rest-api-in-python/
# => http://docs.python-requests.org/en/latest/index.html

# github_url = "https://api.github.com/user/repos"
# data = json.dumps({'name':'test', 'description':'some test repo'}) 
# r = requests.post(github_url, data, auth=('user', '*****'))

# print r.json


class XbmcPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(XbmcPlugin, self).__init__(core, descriptor)

    def terminate(self):
        pass

    def cmd_xbmc(self, args):
        return 'args: ' + ' '.join(args)


descriptor = {
    'name' : 'xbmc',
    'help' : 'Xbmc test module',
    'command' : 'xbmc',
    'mode' : PluginMode.MANAGED,
    'class' : XbmcPlugin
}

