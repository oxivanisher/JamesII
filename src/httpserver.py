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
from functools import wraps

# from OpenSSL import SSL
# context = 'adhoc'
# context = SSL.Context(SSL.SSLv23_METHOD)
# context.use_privatekey_file('yourserver.key')
# context.use_certificate_file('yourserver.crt')

import james

# FIXME:
# - somehow, read the plugin descriptors for nicer display on website
# - support json requests for retrieving data and send commands
# - ssl support

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

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == config['webuser'] and password == config['webpasswd']

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return flask.Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = flask.request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/status')
@requires_auth
def show_status():
    hostnames = {}
    for hostname in DbHostname.query.all():
        hostnames[decode_unicode(hostname.uuid)] = decode_unicode(hostname.hostname)

    systemStatus = {}
    systemStatusAge = {}
    for status in DbStatus.query.all():
        uuid = decode_unicode(status.uuid)
        pluginName = decode_unicode(status.plugin)
        data = decode_multiline_list(status.data)
        time = utils.get_short_age(status.time)

        try:
            systemStatus[uuid]
        except KeyError:
            systemStatus[uuid] = {}

        try:
            systemStatus[uuid][pluginName]
        except KeyError:
            systemStatus[uuid][pluginName] = {}

        try:
            systemStatusAge[uuid]
        except KeyError:
            systemStatusAge[uuid] = {}

        try:
            systemStatusAge[uuid][pluginName]
        except KeyError:
            systemStatusAge[uuid][pluginName] = {}

        systemStatus[uuid][pluginName] = data
        systemStatusAge[uuid][pluginName] = time

    return flask.render_template('status.html', status = systemStatus,
                                                statusAge = systemStatusAge,
                                                hostnames = hostnames )

@app.route('/')
@app.route('/messages')
@requires_auth
def show_messages():

    commandResponses = []
    count = 0
    for response in reversed(DbCommandResponse.query.all()):
        count += 1
        commandResponses.append((convert_Time_to_String(response.time),
                                 decode_multiline_list(response.data),
                                 utils.convert_from_unicode(response.host),
                                 utils.convert_from_unicode(response.plugin)))
        if count >= 5:
            break

    broadcastCommandResponses = []
    count = 0
    for response in reversed(DbBroadcastCommandResponse.query.all()):
        count += 1
        broadcastCommandResponses.append((convert_Time_to_String(response.time),
                                 decode_multiline_list(response.data),
                                 utils.convert_from_unicode(response.host),
                                 utils.convert_from_unicode(response.plugin)))
        if count >= 5:
            break

    alertMessages = []
    count = 0
    for alert in reversed(DbAlertResponse.query.all()):
        count += 1
        alertMessages.append((convert_Time_to_String(alert.time),
                              decode_multiline_list(alert.data)))
        if count >= 5:
            break

    return flask.render_template('messages.html', commandResponses = commandResponses,
                                                  broadcastCommandResponses = broadcastCommandResponses,
                                                  alertMessages = alertMessages )

@app.route('/alerts')
@requires_auth
def show_alerts():

    alertMessages = []
    for alert in reversed(DbAlertResponse.query.all()):
        alertMessages.append((convert_Time_to_String(alert.time),
                              decode_multiline_list(alert.data)))

    return flask.render_template('alerts.html', alertMessages = alertMessages )

@app.route('/commands')
@requires_auth
def show_commands():

    commandResponses = []
    for response in reversed(DbCommandResponse.query.all()):
        commandResponses.append((convert_Time_to_String(response.time),
                                 decode_multiline_list(response.data),
                                 utils.convert_from_unicode(response.host),
                                 utils.convert_from_unicode(response.plugin)))

    return flask.render_template('commands.html', commandResponses = commandResponses )

@app.route('/broadcasts')
@requires_auth
def show_broadcasts():

    broadcastCommandResponses = []
    for response in reversed(DbBroadcastCommandResponse.query.all()):
        broadcastCommandResponses.append((convert_Time_to_String(response.time),
                                 decode_multiline_list(response.data),
                                 utils.convert_from_unicode(response.host),
                                 utils.convert_from_unicode(response.plugin)))

    return flask.render_template('broadcasts.html', broadcastCommandResponses = broadcastCommandResponses )

@app.route('/sendCommand', methods=['GET', 'POST'])
@requires_auth
def send_command():
    if flask.request.method == 'POST':
        if flask.request.form['command'] != "":
            newEntry = DbCommand(json.dumps(flask.request.form['command'].split()), "source")
            db.session.add(newEntry)
            db.session.commit()
        return show_messages()
    else:
        return show_messages()

# @app.route('/todo/api/v1.0/tasks', methods = ['GET'])
# @requires_auth
# def get_tasks():
#     return flask.jsonify( { 'tasks': tasks } )

# @app.route('/todo/api/v1.0/tasks/<int:task_id>', methods = ['GET'])
# @requires_auth
# def get_task(task_id):
#     task = filter(lambda t: t['id'] == task_id, tasks)
#     if len(task) == 0:
#         abort(404)
#     return flask.jsonify( { 'task': task[0] } )

@app.errorhandler(404)
@requires_auth
def not_found(error):
    return flask.make_response(flask.jsonify( { 'error': 'Not found' } ), 404)

@app.route('/static/<string:folderName>/<string:fileName>', methods = ['GET'])
@requires_auth
def get_static(fileName, folderName):
    if fileName:
        return flask.send_from_directory('httpserver/static/' + folderName, fileName)
    else:
        flask.abort(404)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config['webport'])
    # app.run(host='0.0.0.0', ssl_context='adhoc')
