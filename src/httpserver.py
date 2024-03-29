#!/usr/bin/python3
# http://blog.miguelgrinberg.com/post/designing-a-restful-api-with-python-and-flask

import os
import sys
import flask
import time
import json
import datetime
from flask.ext.sqlalchemy import SQLAlchemy
from functools import wraps

# http://www.datatables.net/release-datatables/examples/data_sources/ajax.html

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
    print("Unable to load config")
    sys.exit(1)

if not config['port']:
    config['port'] = 3306
dbConnectionString = "%s://%s:%s@%s:%s/%s" % (config['schema'], config['user'], config['password'], config['host'],
                                              config['port'], config['database'])

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


def convert_Time_to_String(time_input):
    timeInt = int(time_input)
    return datetime.datetime.fromtimestamp(timeInt).strftime('%d.%m.%Y %H:%M:%S')


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


def get_broadcast_responses():
    broadcastCommandResponses = []
    for response in DbBroadcastCommandResponse.query.all():
        broadcastCommandResponses.append((convert_Time_to_String(response.time),
                                          response.data,
                                          utils.convert_from_unicode(response.host),
                                          utils.convert_from_unicode(response.plugin)))
    return broadcastCommandResponses


def get_command_responses():
    commandResponses = []
    for response in DbCommandResponse.query.all():
        commandResponses.append((convert_Time_to_String(response.time),
                                 response.data,
                                 utils.convert_from_unicode(response.host),
                                 utils.convert_from_unicode(response.plugin)))
    return commandResponses


def get_alerts():
    alertMessages = []
    for alert in DbAlertResponse.query.all():
        alertMessages.append((convert_Time_to_String(alert.time),
                              alert.data))
    return alertMessages


@app.route('/status')
@requires_auth
def show_status():
    hostnames = {}
    for hostname in DbHostname.query.all():
        hostnames[hostname.uuid] = hostname.hostname

    systemStatus = {}
    systemStatusAge = {}
    tTime = int(time.time() - 120)
    for status in DbStatus.query.filter(DbStatus.time > tTime):
        myTime = utils.get_short_age(status.time)

        try:
            systemStatus[status.uuid]
        except KeyError:
            systemStatus[status.uuid] = {}

        try:
            systemStatus[status.uuid][status.plugin]
        except KeyError:
            systemStatus[status.uuid][status.plugin] = {}

        try:
            systemStatusAge[status.uuid]
        except KeyError:
            systemStatusAge[status.uuid] = {}

        try:
            systemStatusAge[status.uuid][status.plugin]
        except KeyError:
            systemStatusAge[status.uuid][status.plugin] = {}

        systemStatus[status.uuid][status.plugin] = status.data
        systemStatusAge[status.uuid][status.plugin] = myTime

    return flask.render_template('status.html', status=systemStatus,
                                 statusAge=systemStatusAge,
                                 hostnames=hostnames)


@app.route('/')
@app.route('/messages')
@requires_auth
def show_messages():
    command_responses = []
    count = 0
    for response in reversed(DbCommandResponse.query.all()):
        count += 1
        command_responses.append((convert_Time_to_String(response.time),
                                  response.data,
                                  utils.convert_from_unicode(response.host),
                                  utils.convert_from_unicode(response.plugin)))
        if count >= 5:
            break

    broadcast_command_responses = []
    count = 0
    for response in reversed(DbBroadcastCommandResponse.query.all()):
        count += 1
        broadcast_command_responses.append((convert_Time_to_String(response.time),
                                            response.data,
                                            utils.convert_from_unicode(response.host),
                                            utils.convert_from_unicode(response.plugin)))
        if count >= 5:
            break

    alertMessages = []
    count = 0
    for alert in reversed(DbAlertResponse.query.all()):
        count += 1
        alertMessages.append((convert_Time_to_String(alert.time),
                              alert.data))
        if count >= 5:
            break

    return flask.render_template('messages.html', commandResponses=command_responses,
                                 broadcastCommandResponses=broadcast_command_responses,
                                 alertMessages=alertMessages)


@app.route('/alerts')
@requires_auth
def show_alerts():
    return flask.render_template('alerts.html', alertMessages=get_alerts())


@app.route('/commands')
@requires_auth
def show_commands():
    return flask.render_template('commands.html', commandResponses=get_command_responses())


@app.route('/broadcasts')
@requires_auth
def show_broadcasts():
    return flask.render_template('broadcasts.html', broadcastCommandResponses=get_broadcast_responses())


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


@app.route('/api/get/commands', methods=['GET'])
@requires_auth
def get_command_responses_json():
    print(get_command_responses())
    return flask.jsonify({'aaData': get_command_responses()})


@app.route('/todo/api/v1.0/tasks/<int:task_id>', methods=['GET'])
@requires_auth
def get_task(task_id):
    task = [t for t in tasks if t['id'] == task_id]
    if len(task) == 0:
        abort(404)
    return flask.jsonify({'task': task[0]})


@app.errorhandler(404)
@requires_auth
def not_found(error):
    return flask.make_response(flask.jsonify({'error': 'Not found'}), 404)


@app.route('/static/<string:folderName>/<string:fileName>', methods=['GET'])
@requires_auth
def get_static(file_name, folder_name):
    if file_name:
        return flask.send_from_directory('httpserver/static/' + folder_name, file_name)
    else:
        flask.abort(404)


# main loop
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config['webport'])
    # app.run(host='0.0.0.0', ssl_context='adhoc')
