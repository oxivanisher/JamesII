
import logging
import logging.handlers
import time
import threading
import Queue

from storm.locals import *

class RecordSaverWorkerThread(threading.Thread):
    def __init__(self, queue, config):
        super(RecordSaverWorkerThread, self).__init__()
        print "worker init ..."
        self.config = config
        self.queue = queue

    def connect_db(self):
        self.counter = 0

        print "Connecting to db"
        # self.config = james.config.YamlConfig("../config/netlogger.yaml").get_values()
        if not self.config['port']:
            self.config['port'] = 3306
        self.database = create_database("%s://%s:%s@%s:%s/%s" % (self.config['schema'], self.config['user'], self.config['password'], self.config['host'], self.config['port'], self.config['database']))
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

    def work(self):
        # self.connect_db()
        print "worker work"
        pass

    def run(self):
        result = self.work()
        self.on_exit(result)

    def on_exit(self, result):
        print "worker on_exit"
        pass


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

class LogServerHandler(object):
    def handle_log_record(self, record):
        pass

class RecordSaver(LogServerHandler):
    def __init__(self, config):
        self.config = config
        self.queue = Queue.Queue()
        self.db_thread = RecordSaverWorkerThread(self.queue, self.config)
        print "starting thread"
        self.db_thread.start()
        print "started thread"
        pass

    def handle_log_record(self, record):
        if record:
            print "add record to queue"

class RecordShower(LogServerHandler):
    def __init__(self):
        self.logger = logging.getLogger()
        logging.basicConfig(format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    def handle_log_record(self, record):
        if record:
            self.logger.handle(record)
