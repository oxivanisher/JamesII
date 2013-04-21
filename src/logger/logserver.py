
import cPickle
import logging
import logging.handlers
import SocketServer
import struct
import socket


class LogServerHandler(object):
    def handle_log_record(self, record):
        pass

    def terminate(self):
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

        # print "handle"
        while True:
            # chunk = self.request.recv(4)
            # if len(chunk) < 4:
            #     print "no more data"
            #     return
            # continue
            # slen = struct.unpack(">L", chunk)[0]
            # data = ""
            # while len(data) < slen:
            #     chunk = self.request.recv(slen - len(data))
            #     if len(chunk) == 0:
            #         return
            #     data += chunk
            # obj = self.unPickle(data)
            # record = logging.makeLogRecord(obj)
            # self.handleLogRecord(record)

            #FIXME!! das hier geht, oben wohl nicht
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
        self.terminated = False

    def run(self):
        import select
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.serve_forever()
        except KeyboardInterrupt:
            pass

        self.terminated = True
        self.shutdown()

        for handler in self.handlers:
            handler.terminate()

    def add_handler(self, handler):
        self.handlers.append(handler)
