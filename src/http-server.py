#!/usr/bin/env python
# http://blog.miguelgrinberg.com/post/designing-a-restful-api-with-python-and-flask

import sys
import flask
import signal
from multiprocessing import Process

import james


# class HttpView(flask.views.MethodView):

#     def get(self):
#         print "get recieved"
#         return "get recieved"

#     def post(self):
#         print "post recieved"
#         return "post recieved"


tasks = [
    {
        'id': 1,
        'title': u'Buy groceries',
        'description': u'Milk, Cheese, Pizza, Fruit, Tylenol', 
        'done': False
    },
    {
        'id': 2,
        'title': u'Learn Python',
        'description': u'Need to find a good Python tutorial on the web', 
        'done': False
    }
]


serverApp = flask.Flask(__name__)
# serverApp.add_url_rule('/', view_func=HttpView.as_view('main'), methods=['GET', 'POST'])
serverApp.debug = True

# def on_kill_sig(self, signal, frame):
#     print "signal catched, exiting"
#     core.terminate()

@serverApp.route('/')
def hello_world():
    return 'Hello World!'

@serverApp.route('/todo/api/v1.0/tasks', methods = ['GET'])
def get_tasks():
    return flask.jsonify( { 'tasks': tasks } )

@serverApp.route('/todo/api/v1.0/tasks/<int:task_id>', methods = ['GET'])
def get_task(task_id):
    task = filter(lambda t: t['id'] == task_id, tasks)
    if len(task) == 0:
        abort(404)
    return flask.jsonify( { 'task': task[0] } )

@serverApp.errorhandler(404)
def not_found(error):
    return flask.make_response(flask.jsonify( { 'error': 'Not found' } ), 404)

if __name__ == '__main__':
    print "aa"
    # catch kill signals    
    # signal.signal(signal.SIGTERM,on_kill_sig)
    # signal.signal(signal.SIGQUIT,on_kill_sig)
    # signal.signal(signal.SIGTSTP,on_kill_sig)

    core = james.Core(True)
    core.load_plugin('http-server')
    core.run()
    # core.lock_core()
    # core.run()

    # print core.config

    # go into endless loop
    serverApp.run(host='0.0.0.0')
    # process = Process(target=serverApp.run(host='0.0.0.0'))

    # terminating james core
    # core.unlock_core()
    core.terminate()
