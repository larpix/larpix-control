import time
import zmq

class Serial_ZMQ(object):
    def __init__(self, port, timeout):
        self.port = port
        self.timeout = timeout
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.bind(self.port)

    def open(self):
        pass

    def close(self):
        pass

    def write(self, bytestream):
        '''Send the bytestream.'''
        self.socket.send_multipart([b'0', bytestream])
        self.socket.recv()

    def read(self, timeout=None):
        '''Read for the given duration, in seconds.

           If ``timeout is None``, use ``self.timeout``.
        '''
        timeout = timeout or self.timeout
        self.socket.send_string(str(timeout), flags=zmq.SNDMORE)
        self.socket.send(b'')
        bytestream = self.socket.recv()
        return bytestream

    def write_read(self, bytestream, timeout=None):
        '''Write the given bytestream, then read for the given duration.

           If ``timeout is None``, use ``self.timeout``.
        '''
        timeout = timeout or self.timeout
        self.socket.send_string(str(timeout), flags=zmq.SNDMORE)
        self.socket.send(bytestream)
        new_bytestream = self.socket.recv()
        return new_bytestream
