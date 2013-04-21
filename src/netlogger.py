#!/usr/bin/env python

# needs packages: python-mysqldb python-storm

# import commands
import yaml
import signal
import sys

import james.config
import logger

def on_kill_sig(signal, frame):
    print "Exiting..."
    tcpserver.abort = 1
    sys.exit(0)

def main():
    try:
        tcpserver = logger.logserver.LogServer(host='0.0.0.0')
    except Exception as e:
        print "Socket Error: %s" % e
        sys.exit(1)

    try:
        myconfig = james.config.YamlConfig("../config/netlogger.yaml").get_values()
        print "Saver active: %s; Shower active: %s" % (myconfig['saver_active'], myconfig['shower_active'])
        if myconfig['shower_active']:
            tcpserver.add_handler(logger.loghandler.RecordShower())
        if myconfig['saver_active']:
            tcpserver.add_handler(logger.loghandler.RecordSaver(myconfig))
    except IOError:
        print "No config found. Starting viewer mode only."
        tcpserver.add_handler(logger.loghandler.RecordShower())

    print "About to start TCP Log server reciever"
    tcpserver.run()

    print "Main process ended"
    return 0

if __name__ == "__main__":
    main()
