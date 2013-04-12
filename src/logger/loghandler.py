
import logging
import logging.handlers
import time
import threading
import Queue
import logserver

from storm.locals import *

class RecordSaverWorkerThread(threading.Thread):
    def __init__(self, recordsaver, queue, config):
        super(RecordSaverWorkerThread, self).__init__()
        self.config = config
        self.queue = queue
        self.database = None
        self.store = None
        self.last_store = 0.0
        self.counter = 0
        self.active = True
        self.recordsaver = recordsaver

    def connect_db(self):
        if not self.config['port']:
            self.config['port'] = 3306
        dbConnectionString = "%s://%s:%s@%s:%s/%s" % (self.config['schema'], self.config['user'], self.config['password'], self.config['host'], self.config['port'], self.config['database'])
        print "Connecting to db: %s" % dbConnectionString
        
        self.database = create_database(dbConnectionString)
        self.database.connect()
        self.store = Store(self.database)
        # print "Connected"
        try:
            print self.store.execute("CREATE TABLE log_entries (id INTEGER PRIMARY KEY AUTO_INCREMENT, \
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
            # print "Table created"
        except Exception as e:
            # print "Table not created"
            pass
        self.store.commit()
        self.store.flush()
        self.connecting = False
        print "Connecting ended. Starting to store records."

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
            print "Totally stored records: %10s" % self.counter

    def work(self):
        self.connect_db()

        while self.active:
            try:
                record = self.queue.get_nowait()
                self.save_record(record)
            except Queue.Empty:
                time.sleep(0.5)
                pass
            # i must be able to exit
        pass

    def run(self):
        result = self.work()
        self.on_exit(result)

    def on_exit(self, result):
        print "DB Worker exited"
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

class RecordSaver(logserver.LogServerHandler):
    def __init__(self, config):
        self.config = config
        self.queue = Queue.Queue()
        self.worker_lock = threading.Lock()
        self.db_thread = RecordSaverWorkerThread(self, self.queue, self.config)
        self.db_thread.start()
        pass

    def handle_log_record(self, record):
        if record:
            self.queue.put(record)

class RecordShower(logserver.LogServerHandler):
    def __init__(self):
        self.logger = logging.getLogger()
        logging.basicConfig(format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    def handle_log_record(self, record):
        if record:
            self.logger.handle(record)
