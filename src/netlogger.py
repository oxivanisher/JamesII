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
import time
import signal
import sys
from storm.locals import *

import james.config

class StormLogEntry(object):
    __storm_table__ = "log_entries"
    id              = Int(primary=True)
    relativeCreated = Float()
    process         = Int()
    module          = Unicode()
    funcName        = Unicode()
    message         = Unicode()
    filename        = Unicode()
    levelno         = Int()
    processName     = Unicode()
    lineno          = Int()
    asctime         = Unicode()
    msg             = Unicode()
    args            = Unicode()
    exc_text        = Unicode()
    name            = Unicode()
    thread          = Int()
    created         = Float()
    threadName      = Unicode()
    msecs           = Float()
    pathname        = Unicode()
    exc_info        = Unicode()
    levelname       = Unicode()

    hostname        = Unicode()
    uuid            = Unicode()
    plugin          = Unicode()
    p_child         = Unicode()


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
        # N.B. EVERY record gets logged. This is because Logger.handle
        # is normally called AFTER logger-level filtering. If you want
        # to do filtering, do it at the client end to save wasting
        # cycles and network bandwidth!
        # print "handle record %s" % record

        RecordSaver(record)
        RecordShower(record, self.server)

class RecordShower(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RecordShower, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, record = None, server = None):
        self.server = server
        try:
            self.active
        except:
            self.active = True
            pass

        if not self.active:
            return

        self.render_output(record)

    def render_output(self, record):
        if record:
            if self.server.logname is not None:
                name = self.server.logname
            else:
                name = record.name
            logger = logging.getLogger(name)
            logger.handle(record)

    def set_active(self, state):
        self.active = state

class RecordSaver(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RecordSaver, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, record = None):
        try:
            self.active
        except:
            self.active = True
            pass

        if not self.active:
            return

        try:
            self.connecting
            while self.connecting:
                time.sleep(0.1)
        except:
            pass

        try:
            self.store
        except:
            self.connecting = True
            self.connect_db()
            pass

        if record:
            self.save_record(record)

    def set_active(self, state):
        self.active = state

    def connect_db(self):
        self.counter = 0

        print "Connecting to db"
        myconfig = james.config.YamlConfig("../config/netlogger.yaml").get_values()
        if not myconfig['port']:
            myconfig['port'] = 3306
        self.database = create_database("%s://%s:%s@%s:%s/%s" % (myconfig['schema'], myconfig['user'], myconfig['password'], myconfig['host'], myconfig['port'], myconfig['database']))
        self.store = Store(self.database)
        self.last_store = 0.0
        try:
            self.store.execute("CREATE TABLE log_entries (id INTEGER PRIMARY KEY AUTO_INCREMENT, \
                                                            relativeCreated FLOAT, \
                                                            process INTEGER, \
                                                            module TEXT, \
                                                            funcName TEXT, \
                                                            message TEXT, \
                                                            filename TEXT, \
                                                            levelno TEXT, \
                                                            processName TEXT, \
                                                            lineno INTEGER, \
                                                            asctime TEXT, \
                                                            msg TEXT, \
                                                            args TEXT, \
                                                            exc_text TEXT, \
                                                            name TEXT, \
                                                            thread BIGINT, \
                                                            created FLOAT, \
                                                            threadName TEXT, \
                                                            msecs FLOAT, \
                                                            pathname TEXT, \
                                                            exc_info TEXT, \
                                                            levelname TEXT, \
                                                            hostname TEXT, \
                                                            uuid TEXT, \
                                                            plugin TEXT, \
                                                            p_child TEXT)", noresult=True)
            print "Table created"
        except :
            pass
        self.store.commit()
        self.store.flush()
        self.connecting = False

    def commit_store(self):
        now = time.time()
        if now > self.last_store + 2:
            self.last_store = time.time()
            self.store.commit()
            self.store.flush()

    def save_record(self, record):
        self.counter += 1

        newRecord = StormLogEntry()
        newRecord.relativeCreated     = record.relativeCreated
        newRecord.process             = record.process
        newRecord.module              = unicode(record.module)
        newRecord.funcName            = unicode(record.funcName)
        newRecord.message             = unicode(record.message)
        newRecord.filename            = unicode(record.filename)
        newRecord.levelno             = record.levelno
        newRecord.processName         = unicode(record.processName)
        newRecord.lineno              = record.lineno
        newRecord.asctime             = unicode(record.asctime)
        newRecord.msg                 = unicode(record.msg)
        newRecord.args                = unicode(record.args)
        newRecord.exc_text            = unicode(record.exc_text)
        newRecord.name                = unicode(record.name)
        newRecord.thread              = record.thread
        newRecord.created             = record.created
        newRecord.threadName          = unicode(record.threadName)
        newRecord.msecs               = record.msecs
        newRecord.pathname            = unicode(record.pathname)
        newRecord.exc_info            = unicode(record.exc_info)
        newRecord.levelname           = unicode(record.levelname)

        args = record.name.split('.')
        try:
            newRecord.hostname        = unicode(args[0])
        except:
            newRecord.hostname        = unicode("")
            pass
        try:
            newRecord.uuid            = unicode(args[1])
        except:
            newRecord.uuid            = unicode("")
            pass
        try:
            newRecord.plugin          = unicode(args[2])
        except:
            newRecord.plugin          = unicode("")
            pass
        try:
            newRecord.p_child         = unicode('.'.join(args[3:]))
        except:
            newRecord.p_child         = unicode("")
            pass

        self.store.add(newRecord)
        self.commit_store()
        if (self.counter % 50) == 0:
            print "Totally processed %s messages" % self.counter
   
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

def on_kill_sig(signal, frame):
    print "Exiting..."
    sys.exit(0)

def main():
	#%(relativeCreated)5d

    signal.signal(signal.SIGINT,on_kill_sig)
    signal.signal(signal.SIGTERM,on_kill_sig)
    signal.signal(signal.SIGQUIT,on_kill_sig)

    saver = RecordSaver()
    shower = RecordShower()

    # FIXME: if no config is available, start only viewer
    try:
        myconfig = james.config.YamlConfig("../config/netloggera.yaml").get_values()
        saver.active = myconfig['saver_active']
        shower.active = myconfig['shower_active']
    except IOError:
        print "No config found. Starting viewer mode only."
        saver.active = False
        shower.active = True
        pass

    logging.basicConfig(format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    hostip=commands.getoutput("/sbin/ifconfig | grep -i \"inet\" | grep -iv \"inet6\" | awk {'print $2'} | sed -ne 's/addr\:/ /p' | grep -v '127.0.0.1'").strip()
    tcpserver = LogRecordSocketReceiver(host=hostip)
    print "About to start TCP server on %s:%s..." % (hostip, logging.handlers.DEFAULT_TCP_LOGGING_PORT)
    tcpserver.serve_until_stopped()

if __name__ == "__main__":
    main()

