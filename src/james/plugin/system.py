
import sys
from datetime import timedelta

import commands
from james.plugin import *

class SystemPlugin(Plugin):

    def __init__(self, core):
        super(SystemPlugin, self).__init__(core, SystemPlugin.name)

        self.create_command('echo', self.cmd_echo, 'echos some text')
        self.create_command('quit', self.cmd_quit, 'quitting system')
        self.create_command('version', self.cmd_version, 'shows git checkout version')
        self.create_command('get_node_ip', self.cmd_get_ip, 'get the ip of the node')
        self.create_command('get_node_name', self.cmd_get_node_name, 'get the name of the node')
        self.create_command('get_node_info', self.cmd_get_node_info, 'get the name and ip of the node')


    def terminate(self):
        pass

    def cmd_echo(self, args):
        print 'cmd echo'
        if args.has_key(0):
            args[0] = 'you entered no text to echo...'
        return args[0]

    if os.path.isfile('/usr/bin/git'):
        def cmd_version(self, args):
            version_pipe = os.popen('/usr/bin/git log -n 1 --pretty="format:%h %ci"')
            version = version_pipe.read().strip()
            version_pipe.close()
            return version

    def cmd_get_ip(self, args):
        print 'cmd get_ip'
        return self.get_ip()

    def cmd_get_node_name(self, args):
        print 'cmd get_node_name'
        return self.core.hostname

    def cmd_get_node_info(self, args):
        print 'cmd get_node_info'
        return "%-15s - %s" % (self.get_ip(), self.core.hostname)

    def cmd_quit(self, args):
        print 'JamesII shutting down.'
        #sys.exit(0)
        self.core.terminate()


    # Helper Methods
    def get_ip(self):
        return commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | " +
                         "awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'")


descriptor = {
    'name' : 'system',
    'mode' : PluginMode.AUTOLOAD,
    'class' : SystemPlugin
}

