#!/usr/bin/env python
# http://blog.miguelgrinberg.com/post/designing-a-restful-api-with-python-and-flask

import os
import sys
import flask
import signal
import time
import json
import datetime
from flask.ext.sqlalchemy import SQLAlchemy

import james
# print james.plugin.Factory.descriptors

# factory = james.plugin.Factory()
# factory.autoload_plugins()
# # path = os.path.join(os.path.dirname(__file__), 'plugin')


# print factory.descriptors
# pluginDetailNames = james.plugin.Factory.descriptors
# print pluginDetailNames

utils = james.jamesutils.JamesUtils(None)

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'httpserver/templates')
app = flask.Flask(__name__, template_folder=tmpl_dir)

try:
    cfgFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../config/httpserver.yaml')
    config = james.config.YamlConfig(cfgFile).get_values()
except IOError:
    print "Unable to load config"
    sys.quit(1)

if not config['port']:
    config['port'] = 3306
dbConnectionString = "%s://%s:%s@%s:%s/%s" % (config['schema'], config['user'], config['password'], config['host'], config['port'], config['database'])

app.config['SQLALCHEMY_DATABASE_URI'] = dbConnectionString
db = SQLAlchemy(app)
app.debug = False

class DbCommand(db.Model):
    __tablename__ = 'commands'
    id = db.Column(db.Integer, primary_key=True)
    command = db.Column(db.Text)
    source = db.Column(db.Text)

    def __init__(self, command, source):
        self.command = command
        self.source = source

class DbHostname(db.Model):
    __tablename__ = 'hostnames'
    uuid = db.Column(db.Text, primary_key=True)
    hostname = db.Column(db.Text)

    def __init__(self, uuid, hostname):
        self.uuid = uuid
        self.hostname = hostname

class DbCommandResponse(db.Model):
    __tablename__ = 'commandResponses'
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.Integer)
    host = db.Column(db.Text)
    plugin = db.Column(db.Text)
    data = db.Column(db.Text)

    def __init__(self, time, host, plugin, data):
        self.time = time
        self.host = host
        self.plugin = plugin
        self.data = data

class DbBroadcastCommandResponse(db.Model):
    __tablename__ = 'broadcastCommandResponses'
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.Integer)
    host = db.Column(db.Text)
    plugin = db.Column(db.Text)
    data = db.Column(db.Text)

    def __init__(self, time, host, plugin, data):
        self.time = time
        self.host = host
        self.plugin = plugin
        self.data = data

class DbAlertResponse(db.Model):
    __tablename__ = 'alertResponses'
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.Integer)
    data = db.Column(db.Text)

    def __init__(self, time, data):
        self.time = time
        self.data = data

class DbStatus(db.Model):
    __tablename__ = 'status'
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.Integer)
    uuid = db.Column(db.Text)
    plugin = db.Column(db.Text)
    data = db.Column(db.Text)

    def __init__(self, time, uuid, plugin, data):
        self.time = time
        self.uuid = uuid
        self.plugin = plugin
        self.data = data

def convert_Time_to_String(time):
    timeInt = int(time)
    return datetime.datetime.fromtimestamp(timeInt).strftime('%d.%m.%Y %H:%M:%S')

def decode_multiline_list(data):
    return utils.convert_from_unicode(json.loads(data))

def decode_unicode(data):
    return utils.convert_from_unicode(data)

@app.route('/status')
def show_status():
    hostnames = {}
    for hostname in DbHostname.query.all():
        hostnames[decode_unicode(hostname.uuid)] = decode_unicode(hostname.hostname)

    systemStatus = {}
    for status in DbStatus.query.all():
        uuid = decode_unicode(status.uuid)
        pluginName = decode_unicode(status.plugin)
        data = decode_multiline_list(status.data)

        try:
            systemStatus[uuid]
        except KeyError:
            systemStatus[uuid] = {}

        try:
            systemStatus[uuid][pluginName]
        except KeyError:
            systemStatus[uuid][pluginName] = {}

        systemStatus[uuid][pluginName] = data

    return flask.render_template('status.html', status = systemStatus,
                                                hostnames = hostnames )

@app.route('/')
@app.route('/messages')
def show_responses():
    commandResponses = []
    broadcastCommandResponses = []
    alertMessages = []

    for response in DbCommandResponse.query.all():
        commandResponses.append((convert_Time_to_String(response.time),
                                 decode_multiline_list(response.data),
                                 utils.convert_from_unicode(response.host),
                                 utils.convert_from_unicode(response.plugin)))

    for response in DbBroadcastCommandResponse.query.all():
        broadcastCommandResponses.append((convert_Time_to_String(response.time),
                                 decode_multiline_list(response.data),
                                 utils.convert_from_unicode(response.host),
                                 utils.convert_from_unicode(response.plugin)))

    for alert in DbAlertResponse.query.all():
        alertMessages.append((convert_Time_to_String(alert.time),
                              decode_multiline_list(alert.data)))

    return flask.render_template('messages.html', commandResponses = reversed(commandResponses),
                                                  broadcastCommandResponses = reversed(broadcastCommandResponses),
                                                  alertMessages = reversed(alertMessages) )

@app.route('/sendCommand', methods=['GET', 'POST'])
def send_command():
    if flask.request.method == 'POST':
        if flask.request.form['command'] != "":
            newEntry = DbCommand(json.dumps(flask.request.form['command'].split()), "source")
            db.session.add(newEntry)
            db.session.commit()
        return show_responses()
    else:
        return show_responses()

# @app.route('/todo/api/v1.0/tasks', methods = ['GET'])
# def get_tasks():
#     return flask.jsonify( { 'tasks': tasks } )

# @app.route('/todo/api/v1.0/tasks/<int:task_id>', methods = ['GET'])
# def get_task(task_id):
#     task = filter(lambda t: t['id'] == task_id, tasks)
#     if len(task) == 0:
#         abort(404)
#     return flask.jsonify( { 'task': task[0] } )

@app.errorhandler(404)
def not_found(error):
    return flask.make_response(flask.jsonify( { 'error': 'Not found' } ), 404)

@app.route('/static/<string:folderName>/<string:fileName>', methods = ['GET'])
def get_static(fileName, folderName):
    if fileName:
        return flask.send_from_directory('httpserver/static/' + folderName, fileName)
    else:
        flask.abort(404)

if __name__ == '__main__':
    print ('Starting up webserver')
    app.run(host='0.0.0.0')
    print ('Terminating')
