#!/usr/bin/env python
# http://blog.miguelgrinberg.com/post/designing-a-restful-api-with-python-and-flask

import os
import sys
import flask
import signal
import time

import james

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'http-server/templates')
serverApp = flask.Flask(__name__, template_folder=tmpl_dir)
serverApp.debug = True

@serverApp.route('/status')
def show_status():
    (externalSystemStatus, command_responses, broadcast_command_responses, hostnames) = get_james_data()

    return flask.render_template('status.html', status = externalSystemStatus,
                                               command_responses = command_responses, 
                                               broadcast_command_responses = broadcast_command_responses,
                                               hostnames = hostnames,
                                               pluginDetailNames = pluginDetailNames )

@serverApp.route('/')
@serverApp.route('/commands')
def show_responses():
    (externalSystemStatus, command_responses, broadcast_command_responses, hostnames) = get_james_data()

    return flask.render_template('commands.html', command_responses = command_responses,
                                                   broadcast_command_responses = broadcast_command_responses )

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

@serverApp.route('/static/<string:folderName>/<string:fileName>', methods = ['GET'])
def get_static(fileName, folderName):
    if fileName:
        return flask.send_from_directory('http-server/static/' + folderName, fileName)
    else:
        flask.abort(404)

def get_james_data():
    jamesProcess.core.lock_core()

    externalSystemStatus = jamesPlugin.externalSystemStatus
    hostnames = jamesPlugin.hostnames
    command_responses = jamesPlugin.command_responses
    broadcast_command_responses = jamesPlugin.broadcast_command_responses

    jamesProcess.core.unlock_core()

    return (externalSystemStatus, command_responses, broadcast_command_responses, hostnames)

def get_james_static_data():
    pluginFactoryDescriptors = james.plugin.Factory.descriptors
    return pluginFactoryDescriptors

if __name__ == '__main__':
    # initialize james
    jamesProcess = james.ThreadedCore(True)
    logger = jamesProcess.get_logger('http-server')
    logger.info('Starting up JamesII')
    jamesProcess.start()

    # locate http-server plugin
    jamesProcess.core.load_plugin('http-server')
    for plugin in jamesProcess.core.plugins:
        if plugin.name == 'http-server':
            jamesPlugin = plugin

    # get static informations
    pluginDetailNames = get_james_static_data()

    # go into endless loop
    logger.info('Starting up webserver')
    serverApp.run(host='0.0.0.0')

    # terminating james core
    logger.info('Terminating')
    jamesProcess.terminate()
