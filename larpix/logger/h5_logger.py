import time
import os

import numpy as np
import h5py

from larpix.logger import Logger
from larpix.larpix import Packet, TimestampPacket, DirectionPacket
from larpix.format.hdf5format import to_file, dtypes

class HDF5Logger(Logger):
    '''
    The HDF5Logger is logger class for logging packets to an hdf5 file format.

    The HDF5 file is be formatted as follows:

    *Groups:* ``_header``

        ``_header`` group: contains additional file information within its ``attrs``.
        The available fields are indicated in ``HDF5Logger.header_keys``. The header
        is initialized upon opening the logger.

    *Datasets:* specified by ``HDF5Logger.dataset_list`` and ``HDF5Logger.data_desc_map``

        ``HDF5Logger.dataset_list``: Lists the datasets that are
        produced.

        ``HDF5Logger.data_desc_map``: This maps specifies the mapping between
        larpix core datatypes and the dataset within the HDF5 file. E.g.,
        ``larpix.Packet`` objects are stored in ``'raw_packet'``.

    :param filename: filename to store data (appended to ``directory``)
        (optional, default: ``None``)
    :param buffer_length: how many data messages to hang on to before flushing
        buffer to the file (optional, default: ``10000``)
    :param directory: the directory to save the data in (optional,
        default: '')

    '''
    VERSION = '0.0'
    data_desc_map = {
        Packet: 'raw_packet',
        TimestampPacket: 'raw_packet',
        DirectionPacket: 'raw_packet',
    }
    dataset_list = list(dtypes[VERSION].keys())

    def __init__(self, filename=None, buffer_length=10000,
            directory=''):
        self.filename = filename
        self.directory = directory
        self.datafile = None
        self.buffer_length = buffer_length

        self._buffer = dict([(dataset, []) for dataset in
            self.dataset_list])
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

    def record(self, data, direction=None, timestamp=None, *args, **kwargs):
        '''
        Send the specified data to log file
        .. note:: buffer is flushed after all ``data`` is placed in buffer, this
            means that the buffer size will exceed the set value temporarily

        :param data: list of data to be written to log
        :param direction: optional, 0 if packets were sent to ASICs, 1 if packets
            were received from ASICs. If specified, will add a
            DirectionPacket to the logger.
        :param timestamp: unix timestamp to be associated with data
        '''
        if not self.is_enabled():
            return
        if not self.is_open():
            self.open()
        if not isinstance(data, list):
            raise ValueError('data must be a list')
        if not timestamp:
            timestamp = time.time()

        if direction is not None:
            direction_packet = DirectionPacket(direction)
            dataset = self.data_desc_map[type(direction_packet)]
            self._buffer[dataset].append(direction_packet)
        for data_obj in data:
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
        to_file(self.filename, [], version=self.VERSION)
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
        to_file(self.filename, self._buffer['raw_packet'],
                version=self.VERSION)
        self._buffer['raw_packet'] = []
