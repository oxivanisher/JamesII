#!/usr/bin/env python

# needs packages: python-mysqldb python-storm

import commands
import yaml
import signal
import sys


# branch test juhui


import james.config
import logger

def on_kill_sig(signal, frame):
    print "Exiting..."
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT,on_kill_sig)
    signal.signal(signal.SIGTERM,on_kill_sig)
    signal.signal(signal.SIGQUIT,on_kill_sig)

    hostip=commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'").strip()
    tcpserver = logger.logserver.LogServer(host=hostip)

    try:
        myconfig = james.config.YamlConfig("../config/netlogger.yaml").get_values()
        print "Saver active: %s; Shower active: %s" % (myconfig['saver_active'], myconfig['shower_active'])
        if myconfig['saver_active']:
            tcpserver.add_handler(logger.loghandler.RecordShower())
        if myconfig['shower_active']:
            # tcpserver.add_handler(logger.loghandler.RecordSaver())
            pass
    except IOError:
        print "No config found. Starting viewer mode only."
        tcpserver.add_handler(logger.loghandler.RecordShower())

    print "About to start TCP server"
    tcpserver.serve_until_stopped()

if __name__ == "__main__":
    main()
