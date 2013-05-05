# http://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world

from james.plugin import *

# http://stackoverflow.com/questions/713847/recommendations-of-python-rest-web-services-framework
# http://docs.python.org/2/library/socketserver.html
# http://www.linuxjournal.com/content/tech-tip-really-simple-http-server-python

# http://stackoverflow.com/questions/14444913/web-py-specify-address-and-port


# urls = (
#     '/', 'index'
# )

# class index:
#     def GET(self):
#         return "Hello, world!"

# if __name__ == "__main__":
#     app = web.application(urls, globals())
#     app.run()

    
class HttpServerPlugin(Plugin):

    def __init__(self, core, descriptor):

        super(HttpServerPlugin, self).__init__(core, descriptor)

        self.logger.info("http server loaded")


descriptor = {
    'name' : 'http-server',
    'help' : 'Webfrontend for JamesII',
    'command' : 'http',
    'mode' : PluginMode.MANAGED,
    'class' : HttpServerPlugin,
    'detailsNames' : {}
}
