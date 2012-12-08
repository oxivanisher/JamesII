
import time
import uuid

class JamesMessage (object):

    def __init__(self, core, name):
        self.core = core

        self.timestamp = time.time()

        self.sender_host = core.hostname
        self.sender_uuid = core.uuid
        self.sender_name = name

        self.reciever_host = None
        self.reciever_uuid = None
        self.reciever_name = None

        self.body = ""
        self.header = ""
        self.level = 0 #0: Debug, 1: Info, 2: Warn, 3: Error

        self.payload = None

    def send(self):
        self.core.send_message(self.get())

    def get(self):
        message = {}

        message['timestamp'] = self.timestamp

        message['sender_host'] = self.sender_host
        message['sender_uuid'] = self.sender_uuid
        message['sender_name'] = self.sender_name

        message['reciever_host'] = self.reciever_host
        message['reciever_uuid'] = self.reciever_uuid
        message['reciever_name'] = self.reciever_name

        message['body'] = self.body
        message['header'] = self.header
        message['level'] = self.level
        
        message['payload'] = self.payload

        return message
        
    def set(self, message):
        self.timestamp = message['timestamp']

        self.sender_host = message['sender_host']
        self.sender_uuid = message['sender_uuid']
        self.sender_name = message['sender_name']

        self.reciever_host = message['reciever_host']
        self.reciever_uuid = message['reciever_uuid']
        self.reciever_name = message['reciever_name']

        self.body = message['body']
        self.header = message['header']
        self.level = message['level']

        self.payload = message['payload']
