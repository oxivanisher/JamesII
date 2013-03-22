# http://docs.python.org/2/library/logging.html
# http://docs.python.org/release/2.3.5/lib/node304.html

import os
import logging

class logger(object):

    def __init__(self, name):

        self.filelogger = logging.getLogger(name)
        # hdlr = logging.FileHandler('/tmp/james.log')
        hdlr = logging.FileHandler("./JamesII.log")
        formatter = logging.Formatter('%(asctime)s %(levelname)-7s %(name)s: %(message)s')
        hdlr.setFormatter(formatter)
        self.filelogger.addHandler(hdlr)
        self.filelogger.setLevel(logging.DEBUG)

        self.debug_mode = True

    def setDebug(self, mode):
        if mode:
            self.filelogger.setLevel(logging.DEBUG)
        else:
            self.filelogger.setLevel(logging.WARNING)

    def getLogger(self, name):
        #FIXME: this is wrong
        return logger(name)

    def debug(self, message):
        self.filelogger.debug(message)

    def info(self, message):
        print(message)
        self.filelogger.info(message)

    def warning(self, message):
        print(message)
        self.filelogger.warning(message)

    def error(self, message):
        print(message)
        self.filelogger.error(message)

    def critical(self, message):
        print(message)
        self.filelogger.critical(message)
