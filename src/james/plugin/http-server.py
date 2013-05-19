# http://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world

import flask, flask.views

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

class HttpView(flask.views.MethodView):

    def get(self):
        print "get recieved"
        return "get recieved"

    def post(self):
        print "post recieved"
        return "post recieved"


class HttpServerWorker(PluginThread):

    def __init__(self, plugin):
        super(HttpServerWorker, self).__init__(plugin)
        self.serverApp = flask.Flask(__name__)
        self.serverApp.add_url_rule('/', view_func=HttpView.as_view('main'), methods=['GET', 'POST'])
        self.serverApp.debug = True

        self.logger.debug('HTTP Worker thread initialized')

    def work(self):
        self.logger.debug('HTTP Worker starting')
        self.serverApp.run()
        pass



    
class HttpServerPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(HttpServerPlugin, self).__init__(core, descriptor)

        self.workerThread = HttpServerWorker(self)


    def start(self):
        self.logger.debug('Starting worker')
        self.workerThread.start()
        self.worker_threads.append(self.workerThread)
        

    def terminate(self):
        self.wait_for_threads(self.worker_threads)


descriptor = {
    'name' : 'http-server',
    'help' : 'Webfrontend for JamesII',
    'command' : 'http',
    'mode' : PluginMode.MANAGED,
    'class' : HttpServerPlugin,
    'detailsNames' : {}
}
