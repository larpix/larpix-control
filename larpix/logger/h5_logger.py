import time
import os
import threading
import sys
if sys.version_info[0] >= 3:
    from queue import Queue, Empty
else:
    from Queue import Queue, Empty

import numpy as np
import h5py

from larpix.logger import Logger
from larpix import Packet, TimestampPacket, Packet_v1, Packet_v2, SyncPacket, TriggerPacket
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
        Packet_v1: 'packets',
        Packet_v2: 'packets',
        TimestampPacket: 'packets',
        SyncPacket: 'packets',
        TriggerPacket: 'packets'
    }

    def __init__(self, filename=None, buffer_length=10000,
            directory='', version=latest_version, enabled=False):
        super(HDF5Logger, self).__init__(enabled=enabled)
        self.version = version
        self.filename = filename
        self.directory = directory
        self.datafile = None
        self.buffer_length = buffer_length

        self._buffer = {'packets': []}
        self._worker_queue = Queue()
        self._worker = None
        if not self.filename:
            self.filename = self._default_filename()
        self.filename = os.path.join(self.directory, self.filename)

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

    def record_configs(self, chips):
        '''
        Write the specified chip configurations to the log file

        .. note:: this method will also flush any data in the buffer to the log file

        :param chips: list of chips to record timestamps

        '''
        self.flush(block=True)
        to_file(self.filename, chip_list=chips, version=self.version)

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
        if not isinstance(data, list):
            raise ValueError('data must be a list')

        for data_obj in data:
            data_obj.direction = direction
            dataset = self.data_desc_map[type(data_obj)]
            self._buffer[dataset].append(data_obj)

        if any([len(buff) > self.buffer_length for dataset, buff in self._buffer.items()]):
            self.flush(block=False)

    def enable(self):
        '''
        Enable the logger and set up output file.

        If the file already exists then data will be appended to the end of arrays.

        :param enable: ``True`` if you want to enable the logger after
            initializing (Optional, default=``True``)

        '''
        super(HDF5Logger, self).enable()
        self.flush(block=False)

    def flush(self, block=True):
        self._worker_queue.put(self._buffer['packets'])
        if self._worker is None:
            self._launch_worker()
        if block:
            self._worker_queue.join()
        self._buffer['packets'] = []

    def _launch_worker(self):
        self._worker = threading.Thread(target=self._writer)
        self._worker.start()

    def _writer(self):
        try:
            while True:
                packets = self._worker_queue.get(timeout=1)
                to_file(self.filename, packets, version=self.version)
                self._worker_queue.task_done()
        except Empty:
            pass
        except:
            print('HDF5Logger IO thread error!')
            raise
        finally:
            self._worker = None

