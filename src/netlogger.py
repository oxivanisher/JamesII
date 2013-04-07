#!/usr/bin/env python

# needs packages: python-mysqldb python-storm

import cPickle
import logging
import logging.handlers
import SocketServer
import struct
import socket
import commands
import yaml

import james.config
from storm.locals import *

class StormLogEntry(object):
    __storm_table__ = "logentry"
    id        = Int(primary=True)
    timestamp = Int()
    loglevel  = Unicode()
    uuid      = Unicode()
    hostname  = Unicode()
    plugin    = Unicode()
    p_child   = Unicode()
    message   = Unicode()


# http://docs.python.org/2/howto/logging-cookbook.html#logging-cookbook

class LogRecordStreamHandler(SocketServer.StreamRequestHandler):
    """Handler for a streaming logging request.

    This basically logs the record using whatever logging policy is
    configured locally.
    """

    def handle(self):
        """
        Handle multiple requests - each expected to be a 4-byte length,
        followed by the LogRecord in pickle format. Logs the record
        according to whatever policy is configured locally.
        """
        while 1:
            chunk = self.connection.recv(4)
            if len(chunk) < 4:
                break
            slen = struct.unpack(">L", chunk)[0]
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk = chunk + self.connection.recv(slen - len(chunk))
            obj = self.unPickle(chunk)
            record = logging.makeLogRecord(obj)
            self.handleLogRecord(record)

    def unPickle(self, data):
        return cPickle.loads(data)

    def handleLogRecord(self, record):
        # if a name is specified, we use the named logger rather than the one
        # implied by the record.
        if self.server.logname is not None:
            name = self.server.logname
        else:
            name = record.name
        logger = logging.getLogger(name)
        # N.B. EVERY record gets logged. This is because Logger.handle
        # is normally called AFTER logger-level filtering. If you want
        # to do filtering, do it at the client end to save wasting
        # cycles and network bandwidth!
        logger.handle(record)

class LogRecordSocketReceiver(SocketServer.ThreadingTCPServer):
    """simple TCP socket-based logging receiver suitable for testing.
    """

    allow_reuse_address = 1

    def __init__(self, host='localhost',
                 port=logging.handlers.DEFAULT_TCP_LOGGING_PORT,
                 handler=LogRecordStreamHandler):
        SocketServer.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

    def serve_until_stopped(self):
        import select
        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()],
                                       [], [],
                                       self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort

def main():
	#%(relativeCreated)5d

    print "loading database"
    myconfig = james.config.YamlConfig("../config/netlogger.yaml").get_values()
    if not myconfig['port']:
        myconfig['port'] = 3306
    database = create_database("%s://%s:%s@%s:%s/%s" % (myconfig['schema'], myconfig['user'], myconfig['password'], myconfig['host'], myconfig['port'], myconfig['database']))
    store = Store(database)


    logging.basicConfig(format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    hostip=commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'").strip()
    tcpserver = LogRecordSocketReceiver(host=hostip)
    print "About to start TCP server on %s:%s..." % (hostip, logging.handlers.DEFAULT_TCP_LOGGING_PORT)
    tcpserver.serve_until_stopped()

if __name__ == "__main__":
    main()

