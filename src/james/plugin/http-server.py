

from james.plugin import *

# http://stackoverflow.com/questions/713847/recommendations-of-python-rest-web-services-framework
# http://docs.python.org/2/library/socketserver.html
# http://www.linuxjournal.com/content/tech-tip-really-simple-http-server-python

class HttpServerPlugin(Plugin):

    def __init__(self, core, descriptor):

        super(HttpServerPlugin, self).__init__(core, descriptor)

        print "http server loaded"


descriptor = {
    'name' : 'http-server',
    'help' : 'Webfrontend for JamesII',
    'command' : 'http',
    'mode' : PluginMode.MANAGED,
    'class' : HttpServerPlugin
}
