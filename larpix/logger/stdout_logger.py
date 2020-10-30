from __future__ import print_function
import time

from larpix.logger import Logger

class StdoutLogger(Logger):
    '''
    The StdoutLogger is logger class that acts as a test logger class. All objects
    are displayed according to their string representation and routed to stdout.

    :param buffer_length: how many data messages to hang on to before flushing buffer to stdout
    :param mode: how logger file should be opened (not implemented in ``StdoutLogger``)
    '''
    def __init__(self, filename=None, buffer_length=0, mode='wa',
            enabled=False):
        super(StdoutLogger, self).__init__(enabled=enabled)
        self.filename = filename
        self._buffer = []
        self.buffer_length = buffer_length

    def record(self, data, direction=0):
        '''
        Send the specified data to stdout

        :param data: list of data to be written to log
        :param direction: 0 if packets were sent to ASICs, 1 if packets
            were received from ASICs. optional, default=0
        '''
        if not self.is_enabled():
            return
        if not isinstance(data,list):
            raise ValueError('data must be a list')

        self._buffer += ['Record: {}'.format(str(data_obj)) for data_obj in data]

        if len(self._buffer) > self.buffer_length:
            self.flush()

    def record_configs(self, chips):
        '''
        Print chips configs to stdout

        :param chips: list of chips to print

        '''
        for chip in chips:
            print(chip)
            print(chip.config)
            print()

    def flush(self):
        '''
        Flushes any held data
        '''
        for msg in self._buffer:
            print(msg)
        self._buffer = []
