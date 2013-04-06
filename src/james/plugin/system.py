
import sys
from datetime import timedelta

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

        nodes_command = self.commands.create_subcommand('nodes', 'Activates or deactivates debug output on core', None)
        nodes_command.create_subcommand('info', 'Shows informations', self.cmd_nodes_info)
        nodes_command.create_subcommand('plugins', 'Show the running plugins', self.cmd_nodes_plugins)
        nodes_command.create_subcommand('ip', 'Show the ip', self.get_ip)
        if os.path.isfile('/usr/bin/git'):
            nodes_command.create_subcommand('version', 'Shows the current git checkout HEAD', self.cmd_version)

        self.commands.create_subcommand('proximity', 'Show proximity location and state', self.cmd_show_proximity)

        if self.core.master:
            self.commands.create_subcommand('msg', 'Sends a message (head[;body])', self.cmd_message)
            self.commands.create_subcommand('ping', 'Ping all available nodes over rabbitmq', self.cmd_ping)
            self.commands.create_subcommand('aliases', 'Show command aliases', self.cmd_show_aliases)
            self.commands.create_subcommand('quit', 'Quits the system JamesII. Yes, every node will shut down!', self.cmd_quit)

            nodes_command.create_subcommand('show', 'Shows currently online nodes', self.cmd_nodes_show)

    def get_ip(self, args):
        return [commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | " +
                         "awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'").strip()]

    def start(self):
        try:
            file = open(self.crash_detection_file, 'r')
            timestamp = int(file.read())
            file.close()
            self.logger.debug("Checking for crash restart in %s" % (self.crash_detection_file))
            os.remove(self.crash_detection_file)
            self.logger.info('JamesII started after crash %s' % (self.core.utils.get_nice_age(timestamp)))

            message = self.core.new_message(self.name)
            message.level = 2
            message.header = ("James crash detected on %s %s." % (self.core.hostname, self.core.utils.get_nice_age(timestamp)))
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
            return (["Message could not me sent (%s)" % (e)])

    def cmd_quit(self, args):
        message = self.core.new_message(self.name)
        message.header = ("JamesII shutting down (%s@%s)" % (self.name, self.core.hostname))
        message.level = 2
        message.send()

        self.core.discovery_channel.send(['shutdown', self.core.hostname, self.uuid])

    def cmd_ping(self, args):
        self.core.ping_nodes()

    def cmd_nodes_show(self, args):
        nodes_online_dict = {}
        nodes_online_list = []
        print "nodes_online: %s" % self.core.nodes_online
        for uuid in self.core.nodes_online.keys():
            hostname = self.core.nodes_online[uuid]
            print "found %s" % hostname

            # try:
            nodes_online_dict[hostname] = nodes_online_dict[hostname] + 1
            print "multi"

            # except:
            #     print "first"
            #     nodes_online_dict[hostname] = 1

        for node in nodes_online_dict.keys():
            print "crating for %s" % node
            nodes_online_list.append('%s(%s)' % (node, nodes_online_dict[node]))

        return ['%-2s:' % len(nodes_online_list) + ' '.join(sorted(nodes_online_list))]

    def cmd_nodes_info(self, args):
        role = "Slave"
        if self.core.master:
            role = "Master"
        return ['%10s@%-12s %-6s %-10s %-40s' % (self.core.os_username,
                                                 self.core.hostname,
                                                 role,
                                                 sys.platform,
                                                 self.core.uuid)]

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
            request = self.core.utils.list_unicode_cleanup(command['body'])
        except Exception as e:
            request = False
            pass

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
                command = self.command_aliases[request[0]].split() + args
                self.send_command(command)
                self.logger.info('Processing command alias <%s> (%s)' % (request[0], ' '.join(command)))
            except Exception as e:
                if depth == 0:
                    self.logger.info('Unknown command (%s)' % e)
                    self.send_broadcast(['Currently unknown command on core (%s)' % e])
                pass

descriptor = {
    'name' : 'system',
    'help' : 'JamesII system commands',
    'command' : 'sys',
    'mode' : PluginMode.AUTOLOAD,
    'class' : SystemPlugin
}
