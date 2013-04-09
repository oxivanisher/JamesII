
import cPickle
import logging
import logging.handlers
import SocketServer
import struct
import threading

class LogWorkerThread(threading.thread):
    def __init__(self):
        super(LogWorkerThread, self).__init__()
        self.blah

class LogServerHandler(object):
    def handle_log_record(self, record):
        pass

class LogServerRequestHandler(SocketServer.StreamRequestHandler):
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
        for handler in self.server.handlers:
            handler.handle_log_record(record)

class LogServer(SocketServer.ThreadingTCPServer):
    """simple TCP socket-based logging receiver suitable for testing.
    """

    allow_reuse_address = 1

    def __init__(self, host='localhost',
                 port=logging.handlers.DEFAULT_TCP_LOGGING_PORT):
        SocketServer.ThreadingTCPServer.__init__(self, (host, port), LogServerRequestHandler)
        self.abort = 0
        self.timeout = 1
        self.logname = None
        self.handlers = []

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

    def add_handler(self, handler):
        self.handlers.append(handler)