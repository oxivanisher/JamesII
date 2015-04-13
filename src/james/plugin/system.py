
import sys
import socket
import time
# from datetime import timedelta

import commands
from james.plugin import *

class SystemPlugin(Plugin):

    def __init__(self, core, descriptor):
        super(SystemPlugin, self).__init__(core, descriptor)

        self.crash_detection_file = os.path.join(os.getcwd(), ".james_crashed")
        self.command_aliases = self.core.config['core']['command_aliases']

        core_debug_command = self.commands.create_subcommand('core_debug', 'Activates or deactivates debug output on core', None)
        core_debug_command.create_subcommand('on', 'Activate debug', self.cmd_activate_core_debug)
        core_debug_command.create_subcommand('off', 'Deactivate debug', self.cmd_deactivate_core_debug)

        nodes_command = self.commands.create_subcommand('nodes', 'Informational node functions', None)
        nodes_command.create_subcommand('plugins', 'Show the running plugins', self.cmd_nodes_plugins)
        nodes_command.create_subcommand('ip', 'Show the ip', self.get_ip)
        nodes_command.create_subcommand('uptime', 'Show the node uptime', self.get_uptime)
        if os.path.isfile('/usr/bin/git'):
            nodes_command.create_subcommand('version', 'Shows the current git checkout HEAD', self.cmd_version)

        self.commands.create_subcommand('proximity', 'Show proximity location and state', self.cmd_show_proximity)

        if self.core.master:
            self.commands.create_subcommand('msg', 'Sends a message (head[;body])', self.cmd_message)
            self.commands.create_subcommand('ping', 'Ping all available nodes over rabbitmq', self.cmd_ping)
            self.commands.create_subcommand('aliases', 'Show command aliases', self.cmd_show_aliases)
            self.commands.create_subcommand('quit', 'Quits the system JamesII. Yes, every node will shut down!', self.cmd_quit)

            nodes_command.create_subcommand('show', 'Shows currently online nodes', self.cmd_nodes_show)

        self.commands.create_subcommand('allstatus', "Returns detailed system informations", self.cmd_get_details)
        self.data_commands.create_subcommand('allstatus', 'Returns detailed system informations', self.get_data_details)

    def get_ip(self, args):
        return [commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | " +
                         "awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'").strip()]

    def get_uptime(self, args):
        return ["JamesII started " + self.utils.get_nice_age(self.core.startup_timestamp)]

    def start(self):
        try:
            file = open(self.crash_detection_file, 'r')
            timestamp = int(file.read())
            file.close()
            self.logger.debug("Checking for crash restart in %s" % (self.crash_detection_file))
            os.remove(self.crash_detection_file)
            self.logger.info('JamesII started after crash %s' % (self.utils.get_nice_age(timestamp)))

            message = self.core.new_message(self.name)
            message.level = 2
            message.header = ("James crash detected on %s %s." % (self.core.hostname, self.utils.get_nice_age(timestamp)))
            message.send()

        except IOError:
            pass
        pass

    def cmd_show_proximity(self, args):
        return (["%-10s %-10s %s" % (self.core.hostname,
                                  self.core.proximity_status.get_status_here(),
                                  self.core.location)])

    def cmd_activate_core_debug(self, args):
        self.core.logger.info('Activating core debug')
        self.core.logger.setLevel(logging.DEBUG)

    def cmd_deactivate_core_debug(self, args):
        self.core.logger.info('Deactivating core debug')
        self.core.logger.setLevel(logging.INFO)

    def cmd_version(self, args):
        version_pipe = os.popen('/usr/bin/git log -n 1 --pretty="format:%h %ci"')
        version = version_pipe.read().strip()
        version_pipe.close()
        return [version]

    def cmd_message(self, args):
        message_string = ' '.join(args)
        message_list = message_string.split(';')

        message = self.core.new_message("cli_message")
        message.level = 1
        try:
            message.body = message_list[1].strip()
        except IndexError:
            message.body = None

        try:
            message.header = message_list[0].strip()
            message.send()
            return (["Message header: %s; body: %s" % (message.header, message.body)])
        except Exception as e:
            return (["Message could not be sent (%s)" % (e)])

    def cmd_quit(self, args):
        message = self.core.new_message(self.name)
        message.header = ("Bye bye, james is shutting down.")
        message.level = 2
        message.send()

        self.core.discovery_channel.send(['shutdown', self.core.hostname, self.uuid])

    def cmd_ping(self, args):
        self.core.ping_nodes()

    def cmd_nodes_show(self, args):
        nodes_online_dict = {}
        nodes_online_list = []
        for uuid in self.core.nodes_online.keys():
            hostname = self.core.nodes_online[uuid]
            try:
                nodes_online_dict[hostname]
            except:
                nodes_online_dict[hostname] = 0
            nodes_online_dict[hostname] += 1

        for node in nodes_online_dict.keys():
            nodes_online_list.append('%s(%s)' % (node, nodes_online_dict[node]))

        return ['[%s] ' % len(nodes_online_list) + ' '.join(sorted(nodes_online_list))]

    def cmd_get_details(self, args):
        # if plugin == 'system':
        ret = []
        displayData = []
        allData = self.get_data_details([])
        for pluginName in sorted(allData.keys()):
            pluginData = []
            if allData[pluginName]:
                args = allData[pluginName]
                for key in sorted(args.keys()):
                    pluginData.append((Factory.descriptors[pluginName]['detailsNames'][key], args[key]))
                
                displayData.append((pluginName, pluginData))

        for (plugin, pluginData) in displayData:
            for (key, value) in pluginData:
                ret.append("%-15s %-30s %s" % (plugin, key, value))

        return ret

    def get_data_details(self, args):
        ret = {}

        for plugin in self.core.plugins:
            pluginData = plugin.return_status()
            if pluginData:
                ret[plugin.name] = pluginData
        return ret

    def alert(self, args):
        for plugin in self.core.plugins:
            if plugin != self:
                plugin.alert(args)

    def cmd_nodes_plugins(self, args):
        plugin_names = []
        for p in self.core.plugins:
            plugin_names.append(p.name)
        plugin_names.sort()
        return([', '.join(plugin_names)])

    def cmd_show_aliases(self, args):
        ret = []
        for command in sorted(self.command_aliases.keys()):
            ret.append("%-10s %s" % (command, self.command_aliases[command]))
        return ret

    # call from core for requests
    # only the master should process aliases
    def process_command_request_event(self, command):
        try:
            request = self.utils.list_unicode_cleanup(command['body'])
        except Exception as e:
            request = False

        if self.core.master:
            # search in ghost commands
            depth = 0
            try:
                depth = self.core.ghost_commands.get_best_match(request).get_depth()
            except Exception:
                pass

            args = []
            if request:
                if len(request) > 1:
                    args = request[1:]

            try:
                srcUuid = command['uuid']
                runCommand = self.command_aliases[request[0]].split() + args
                self.send_command(runCommand, srcUuid)
                self.logger.info('Processing command alias <%s> (%s)' % (request[0], ' '.join(runCommand)))
            except KeyError as e:
                if depth == 0 and self.core.data_commands.get_best_match(request) != self.core.data_commands:
                    self.logger.info('Unknown command (%s)' % e)
                    self.send_broadcast(['Currently unknown command on core (%s)' % e])

    def return_status(self):
        coreData = {}
        coreData['master'] = self.core.master
        coreData['uuid'] = self.core.uuid
        coreData['ip'] = self.get_ip([])
        coreData['startupTimestamp'] = self.core.startup_timestamp
        coreData['fqdn'] = socket.getfqdn()
        coreData['location'] = self.core.location
        coreData['platform'] = sys.platform
        coreData['osUsername'] = self.core.os_username
        coreData['now'] = time.time()
        coreData['proximityStatus'] = self.core.proximity_status.get_status_here()
        coreData['personsStatus'] = self.core.persons_status
        return coreData

descriptor = {
    'name' : 'system',
    'help' : 'JamesII system commands',
    'command' : 'sys',
    'mode' : PluginMode.AUTOLOAD,
    'class' : SystemPlugin,
    'detailsNames' : { 'master' : "Master mode",
                       'uuid' : "UUID",
                       'ip' : "IPs",
                       'startupTimestamp' : "JamesII Startup",
                       'fqdn' : "Fully qualified domainname",
                       'location' : "Proximity location",
                       'platform' : "Platform",
                       'osUsername' : "OS Username",
                       'now' : "Now Timestamp",
                       'proximityStatus' : "Proximity status on location",
                       'personsStatus': "Persons location status" }
}
