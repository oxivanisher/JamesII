import time


class JamesMessage(object):

    def __init__(self, core, name):
        self.core = core

        self.timestamp = time.time()

        self.sender_host = core.hostname
        self.sender_uuid = core.uuid
        self.sender_name = name

        self.receiver_host = None
        self.receiver_uuid = None
        self.receiver_name = None

        self.body = ""
        self.header = ""
        self.level = 0  # 0: Debug, 1: Info, 2: Warn, 3: Error

        self.payload = None

    def send(self):
        if self.level == 0:
            if self.core.config['core']['debug']:
                self.core.send_message(self.get())
        else:
            self.core.add_timeout(0, self.core.send_message, self.get())

    def get(self):
        message = {'timestamp': self.timestamp, 'sender_host': self.sender_host, 'sender_uuid': self.sender_uuid,
                   'sender_name': self.sender_name, 'receiver_host': self.receiver_host,
                   'receiver_uuid': self.receiver_uuid, 'receiver_name': self.receiver_name, 'body': self.body,
                   'header': self.header, 'level': self.level, 'payload': self.payload}

        return message

    def set(self, message):
        self.timestamp = message['timestamp']

        self.sender_host = message['sender_host']
        self.sender_uuid = message['sender_uuid']
        self.sender_name = message['sender_name']

        self.receiver_host = message['receiver_host']
        self.receiver_uuid = message['receiver_uuid']
        self.receiver_name = message['receiver_name']

        self.body = message['body']
        self.header = message['header']
        self.level = message['level']

        self.payload = message['payload']
