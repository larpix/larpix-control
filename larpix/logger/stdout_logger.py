from __future__ import print_function
import time

from larpix.larpix import Packet

class StdoutLogger(object):
    '''
    The StdoutLogger is logger class that acts as a test logger class. All objects
    are displayed according to their string representation and routed to stdout.

    :param buffer_length: how many data messages to hang on to before flushing buffer to stdout
    :param mode: how logger file should be opened (not implemented in ``StdoutLogger``)
    '''
    def __init__(self, filename=None, buffer_length=0, mode='wa'):
        self.filename = filename
        self._buffer = []
        self._is_enabled = False
        self._is_open = False
        self.buffer_length = buffer_length

    def record(self, data, timestamp=None, *args, **kwargs):
        '''
        Send the specified data to stdout

        :param data: list of data to be written to log
        :param timestamp: unix timestamp to be associated with data
        '''
        if not self._is_enabled:
            return
        if not self._is_open:
            self.open()
        if not isinstance(data,list):
            raise ValueError('data must be a list')
        if not timestamp:
            timestamp = time.time()

        self._buffer += ['Record {}: {}'.format(timestamp, str(data_obj)) for data_obj in data]

        if len(self._buffer) > self.buffer_length:
            self.flush()

    def is_enabled(self):
        '''
        Check if logger is enabled
        '''
        return self._is_enabled

    def enable(self):
        '''
        Allow the logger to record data
        '''
        self._is_enabled = True

    def disable(self):
        '''
        Stop the logger from recording data without closing
        '''
        self.flush()
        self._is_enabled = False

    def is_open(self):
        '''
        Check if logger is open
        '''
        return self._is_open

    def open(self, enable=True):
        '''
        Open logger if it is not already

        :param enable: ``True`` if you want to enable the logger after opening
        '''
        self._is_open = True
        self._is_enabled = enable

    def close(self):
        '''
        Close logger if it is not already

        .. note:: This flushes any data in the buffer before closing
        '''
        self.flush()
        self._is_open = False
        self._is_enabled = False

    def flush(self):
        '''
        Flushes any held data
        '''
        for msg in self._buffer:
            print(msg)
        self._buffer = []
