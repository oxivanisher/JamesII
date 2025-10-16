import os
import time
import json
from storm.locals import *
from storm.expr import *

import james
from james.plugin import *


# http://stackoverflow.com/questions/713847/recommendations-of-python-rest-web-services-framework
# http://docs.python.org/2/library/socketserver.html
# http://www.linuxjournal.com/content/tech-tip-really-simple-http-server-python

# http://stackoverflow.com/questions/14444913/web-py-specify-address-and-port


class DbCommand(object):
    __storm_table__ = "commands"
    id = Int(primary=True)
    command = Unicode()
    source = Unicode()


class DbHostname(object):
    __storm_table__ = "hostnames"
    uuid = Unicode(primary=True)
    hostname = Unicode()


class DbCommandResponse(object):
    __storm_table__ = "commandResponses"
    id = Int(primary=True)
    time = Int()
    host = Unicode()
    plugin = Unicode()
    data = Unicode()


class DbBroadcastCommandResponse(object):
    __storm_table__ = "broadcastCommandResponses"
    id = Int(primary=True)
    time = Int()
    host = Unicode()
    plugin = Unicode()
    data = Unicode()


class DbAlertResponse(object):
    __storm_table__ = "alertResponses"
    id = Int(primary=True)
    time = Int()
    data = Unicode()


class DbStatus(object):
    __storm_table__ = "status"
    id = Int(primary=True)
    time = Int()
    uuid = Unicode()
    plugin = Unicode()
    data = Unicode()


class HttpServerPlugin(Plugin):

    def __init__(self, core, descriptor):
        super().__init__(core, descriptor)

        self.update_timeout = 60
        try:
            self.update_timeout = int(self.config['update_timeout'])
        except Exception:
            pass

        if not self.init_db():
            self.logger.info('Unable to get Database Store. Terminating!')
            self.core.terminate()

        self.node_update_loop()
        self.send_waiting_commands_loop()
        self.store = False

    def init_db(self):
        try:
            cfgFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../config/httpserver.yaml')
            config = james.config.YamlConfig(cfgFile).get_values()
        except IOError:
            return False

        if not config['port']:
            config['port'] = 3306
        dbConnectionString = f"{config['schema']}://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"

        database = create_database(dbConnectionString)
        try:
            database.connect()
            self.store = Store(database)
        except Exception as e:
            return False

        try:
            self.store.execute("CREATE TABLE commands (id INTEGER PRIMARY KEY AUTO_INCREMENT, command TEXT, "
                               "source TEXT)", noresult=True)
        except Exception as e:
            pass
        try:
            self.store.execute("CREATE TABLE hostnames (uuid VARCHAR(255) UNIQUE, hostname TEXT)", noresult=True)
        except Exception as e:
            pass
        try:
            self.store.execute("CREATE TABLE commandResponses (id INTEGER PRIMARY KEY AUTO_INCREMENT, time INTEGER, "
                               "host TEXT, plugin TEXT, data TEXT)", noresult=True)
        except Exception as e:
            pass
        try:
            self.store.execute("CREATE TABLE broadcastCommandResponses (id INTEGER PRIMARY KEY AUTO_INCREMENT, "
                               "time INTEGER, host TEXT, plugin TEXT, data TEXT)", noresult=True)
        except Exception as e:
            pass
        try:
            self.store.execute("CREATE TABLE alertResponses (id INTEGER PRIMARY KEY AUTO_INCREMENT, time INTEGER, "
                               "data TEXT)", noresult=True)
        except Exception as e:
            pass
        try:
            self.store.execute("CREATE TABLE status (id INTEGER PRIMARY KEY AUTO_INCREMENT, time INTEGER, "
                               "uuid TEXT, plugin TEXT, data TEXT)", noresult=True)
        except Exception as e:
            pass

        self.store.commit()
        self.store.flush()
        return True

    # looping stuff
    def request_all_nodes_details(self):
        self.core.add_timeout(0, self.send_data_request, 'status')

    def node_update_loop(self):
        self.request_all_nodes_details()
        self.core.add_timeout(self.update_timeout, self.node_update_loop)

    def send_waiting_commands(self):
        try:
            result = self.store.find(DbCommand)
            for command in result:
                plainCommand = self.utils.convert_from_unicode(json.loads(command.command))
                self.logger.info(f"Running command: {' '.join(plainCommand)}")
                self.send_command(plainCommand)
            result.remove()
            self.store.commit()
        except Exception as e:
            self.logger.error(f'Error: {e}')

    def send_waiting_commands_loop(self):
        self.send_waiting_commands()
        self.core.add_timeout(1, self.send_waiting_commands_loop)

    # internal commands
    def process_command_response(self, args, host, plugin):
        newEntry = DbCommandResponse()
        newEntry.time = int(time.time())
        newEntry.host = str(host)
        newEntry.plugin = str(plugin)
        newEntry.data = str(json.dumps(args))
        self.store.add(newEntry)
        self.store.commit()
        self.logger.debug(f'Saved command response from {host}')

    def process_broadcast_command_response(self, args, host, plugin):
        newEntry = DbBroadcastCommandResponse()
        newEntry.time = int(time.time())
        newEntry.host = str(host)
        newEntry.plugin = str(plugin)
        newEntry.data = str(json.dumps(args))
        self.store.add(newEntry)
        self.store.commit()
        self.logger.debug(f'Saved broadcast command response from {host}')

    def process_data_response(self, uuid, name, current_status, hostname, plugin):
        if name == 'status':
            existingUuid = self.store.get(DbHostname, str(uuid))
            if not existingUuid:
                newEntry = DbHostname()
                newEntry.uuid = str(uuid)
                newEntry.hostname = str(hostname)
                self.store.add(newEntry)
                self.store.commit()
                self.logger.debug(f'Processed new Host UUID: {hostname} {uuid}')

            result = self.store.find(DbStatus, And(DbStatus.uuid == str(uuid), DbStatus.plugin == str(plugin))).one()
            if result:
                result.time = int(time.time())
                result.data = str(json.dumps(current_status))
            else:
                newEntry = DbStatus()
                newEntry.uuid = str(uuid)
                newEntry.plugin = str(plugin)
                newEntry.time = int(time.time())
                newEntry.data = str(json.dumps(current_status))
                self.store.add(newEntry)
            self.store.commit()
            self.logger.debug(f'Processed data status update from {plugin}@{hostname} ({uuid})')

    def alert(self, args):
        newEntry = DbAlertResponse()
        newEntry.data = str(json.dumps(' '.join(args).split(';')))
        newEntry.time = int(time.time())
        self.store.add(newEntry)
        self.store.commit()

    def terminate(self):
        self.store.flush()


descriptor = {
    'name': 'httpserver-plugin',
    'help_text': 'Web-frontend for JamesII',
    'command': 'http',
    'mode': PluginMode.MANAGED,
    'class': HttpServerPlugin,
    'detailsNames': {}
}
