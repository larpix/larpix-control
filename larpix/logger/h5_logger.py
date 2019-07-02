import time
import os

import numpy as np
import h5py

from larpix.logger import Logger
from larpix.larpix import Packet, TimestampPacket
from larpix.format.hdf5format import to_file, latest_version

class HDF5Logger(Logger):
    '''
    The HDF5Logger is a logger class for logging packets to the LArPix+HDF5 format.

    The file format is implemented in ``larpix.format.hdf5format``,
    which also contains a function to convert back from LArPix+HDF5 to
    LArPix packets.

    :var data_desc_map: specifies the mapping between
        objects sent to the logger and the specific logger buffer to store them
        in. As of LArPix+HDF5 version 1.0 and larpix-control version
        2.3.0 there is only one buffer called ``'packets'`` which stores
        all of the data to send to LArPix+HDF5.

    :param filename: filename to store data (appended to ``directory``)
        (optional, default: ``None``)
    :param buffer_length: how many data messages to hang on to before flushing
        buffer to the file (optional, default: ``10000``)
    :param directory: the directory to save the data in (optional,
        default: '')
    :param version: the format version of LArPix+HDF5 to use (optional,
        default: ``larpix.format.hdf5format.latest_version``)

    '''
    data_desc_map = {
        Packet: 'packets',
        TimestampPacket: 'packets',
    }

    def __init__(self, filename=None, buffer_length=10000,
            directory='', version=latest_version):
        self.version = version
        self.filename = filename
        self.directory = directory
        self.datafile = None
        self.buffer_length = buffer_length

        self._buffer = {'packets': []}
        self._is_enabled = False
        self._is_open = False

    def _default_filename(self, timestamp=None):
        '''
        Fetch the default filename based on a timestamp

        :param timestamp: tuple or ``struct_time`` representing a timestamp
        '''
        log_prefix = 'datalog'
        time_format = '%Y_%m_%d_%H_%M_%S_%Z'
        if not timestamp:
            log_specifier = time.strftime(time_format)
        else:
            log_specifier = time.strftime(time_format, timestamp)
        log_postfix = '.h5'
        return (log_prefix + '_' + log_specifier + '_' + log_postfix)

    def record(self, data, direction=Logger.WRITE):
        '''
        Send the specified data to log file

        .. note:: buffer is flushed after all ``data`` is placed in buffer, this
            means that the buffer size will exceed the set value temporarily

        :param data: list of data to be written to log
        :param direction: ``Logger.WRITE`` if packets were sent to
            ASICs, ``Logger.READ`` if packets
            were received from ASICs. (default: ``Logger.WRITE``)

        '''
        if not self.is_enabled():
            return
        if not self.is_open():
            self.open()
        if not isinstance(data, list):
            raise ValueError('data must be a list')

        for data_obj in data:
            data_obj.direction = direction
            dataset = self.data_desc_map[type(data_obj)]
            self._buffer[dataset].append(data_obj)

        if any([len(buff) > self.buffer_length for dataset, buff in self._buffer.items()]):
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
        if self.is_enabled():
            return
        self._is_enabled = True

    def disable(self):
        '''
        Stop the logger from recording data without closing file

        .. note:: This flushes any data in the buffer before closing

        '''
        if not self.is_enabled():
            return
        self.flush()
        self._is_enabled = False

    def is_open(self):
        '''
        Check if logger is open
        '''
        return self._is_open

    def open(self, enable=True):
        '''
        Open output file if it is not already. If files already exist then data
        will be appended to the end of arrays.

        :param enable: ``True`` if you want to enable the logger after opening
            (Optional, default=``True``)
        '''
        if self.is_open():
            return
        if not self.filename:
            self.filename = self._default_filename()
        self.filename = os.path.join(self.directory, self.filename)
        to_file(self.filename, [], version=self.version)
        self._is_open = True
        self._is_enabled = enable

    def close(self):
        '''
        Close logger if it is not already

        .. note:: This flushes any data in the buffer before closing
        '''
        if not self.is_open():
            return
        self.flush()
        self._is_open = False
        self._is_enabled = False

    def flush(self):
        '''
        Flushes any held data to the output file
        '''
        if not self.is_open():
            return
        to_file(self.filename, self._buffer['packets'],
                version=self.version)
        self._buffer['packets'] = []
