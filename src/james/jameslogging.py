# http://docs.python.org/2/library/logging.html
# http://docs.python.org/release/2.3.5/lib/node304.html
# http://stackoverflow.com/questions/7621897/python-logging-module-globally

import os
import logging

class logger(object):

    def __init__(self, name):
    # def setup_custom_logger(name):
        # print "new logger: %s" % name

        # %(module)s
        file_formatter = logging.Formatter('%(asctime)s %(levelname)-7s %(name)s: %(message)s')
        screen_formatter = logging.Formatter('%(message)s')

        self.log = logging.getLogger(name)
        self.log.setLevel(logging.DEBUG)

        # screen handler
        streamhandler = logging.StreamHandler()
        streamhandler.setLevel(logging.INFO)
        streamhandler.setFormatter(screen_formatter)
        self.log.addHandler(streamhandler)

        # file handler
        try:
            filehandler = logging.FileHandler("./JamesII.log")
            filehandler.setLevel(logging.DEBUG)
            filehandler.setFormatter(file_formatter)
            self.log.addHandler(filehandler)
        except Exception:
            self.log.warning("WARNING: Unable to open Logfile for writing")
            pass

    # return log


    # def setDebug(self, mode):
    #     if mode:
    #         streamhandler(logging.DEBUG)
    #     else:
    #         streamhandler(logging.WARNING)

    def getLogger(self, name):
        # newlogger = log.getLogger('core.%s' % name)
        # return newlogger

        #FIXME: this is wrong
        return logging.getLogger(name)

    def debug(self, message):
        self.log.debug(message)

    def info(self, message):
        self.log.info(message)

    def warning(self, message):
        self.log.warning(message)

    def error(self, message):
        self.log.error(message)

    def critical(self, message):
        self.log.critical(message)

    def exception(self, message):
        self.log.exception(message)