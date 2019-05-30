import time
import numpy as np
import h5py

from larpix.larpix import Packet

class HDF5Logger(object):
    '''
    The HDF5Logger is logger class for logging packets to an hdf5 file format.

    :param filename: filename to store data (optional, default: ``None``)
    :param buffer_length: how many data messages to hang on to before flushing
        buffer to the file (optional, default: ``10000``)
    '''
    VERSION = '0.0'
    header_keys = ['version','created']
    data_desc_map = {
        Packet: 'raw_packet'
    }
    data_desc = {
        'raw_packet' : [
            ('record_timestamp','f8'),
            ('chip_key','S32'),
            ('type','i8'),
            ('chipid','i8'),
            ('parity','i1'),
            ('valid_parity','i1'),
            ('counter','i8'),
            ('channel','i8'),
            ('timestamp','i8'),
            ('adc_counts','i8'),
            ('fifo_half','i1'),
            ('fifo_full','i1'),
            ('register','i8'),
            ('value','i8')
        ]
    }

    def __init__(self, filename=None, buffer_length=10000):
        self.filename = filename
        self.datafile = None
        self.buffer_length = buffer_length

        self._buffer = dict([(dataset, []) for dataset in self.data_desc.keys()])
        self._write_idx = dict([(dataset, 0) for dataset in self.data_desc.keys()])
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

    def _create_header(self):
        '''
        Create datafile header

        '''
        if not self.is_open():
            return
        if '_header' in self.datafile.keys():
            return
        header = self.datafile.create_group('_header')
        for header_key in self.header_keys:
            if header_key == 'version':
                header.attrs[header_key] = self.VERSION
            elif header_key == 'created':
                header.attrs[header_key] = time.time()

    def _create_datasets(self):
        '''
        Create any missing datasets in file according to ``data_desc``

        '''
        if not self.is_open():
            return
        for dataset_name in self.data_desc.keys():
            if not dataset_name in self.datafile.keys():
                self.datafile.create_dataset(dataset_name, (0,), maxshape=(None,),
                    dtype=self.data_desc[dataset_name])

    @classmethod
    def encode(cls, data, *args, **kwargs):
        '''
        Converts data object into a numpy mixed type array as described by
        ``data_desc``

        '''
        if not isinstance(data, (Packet)):
            raise ValueError('h5_logger can only encode Packet objects')
        if isinstance(data, Packet):
            return cls.encode_packet(data, *args, **kwargs)

    @classmethod
    def encode_packet(cls, packet, timestamp=None, *args, **kwargs):
        '''
        Converts packets into numpy mixed typ array according to ``data_desc['raw_packet']``

        '''
        if not isinstance(packet, Packet):
            raise ValueError('packet must be of type Packet')
        dict_rep = packet.export()
        data_list = []
        for key, dtype in cls.data_desc['raw_packet']:
            if key == 'record_timestamp':
                if timestamp:
                    data_list += [timestamp]
                else:
                    data_list += [-1]
            elif key == 'chip_key':
                data_list += [str(dict_rep['chip_key'])]
            elif key in dict_rep:
                if key == 'type':
                    data_list += [int(packet.packet_type.to01(), 2)]
                else:
                    data_list += [dict_rep[key]]
            else:
                data_list += [-1]
        return np.array(tuple(data_list),dtype=cls.data_desc['raw_packet'])

    def record(self, data, timestamp=None, *args, **kwargs):
        '''
        Send the specified data to log file
        .. note:: buffer is flushed after all ``data`` is placed in buffer, this
            means that the buffer size will exceed the set value temporarily

        :param data: list of data to be written to log
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

        for data_obj in data:
            dataset = self.data_desc_map[type(data_obj)]
            self._buffer[dataset] += [self.encode(data_obj, timestamp=timestamp)]

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
        self.datafile = h5py.File(self.filename)
        self._is_open = True
        self._is_enabled = enable

        self._create_header()
        self._create_datasets()
        for dataset in self.data_desc.keys():
            self._write_idx[dataset] = self.datafile[dataset].shape[0]

    def close(self):
        '''
        Close logger if it is not already

        .. note:: This flushes any data in the buffer before closing
        '''
        if not self.is_open():
            return
        self.flush()
        self.datafile.close()
        self._is_open = False
        self._is_enabled = False

    def flush(self):
        '''
        Flushes any held data to the output file
        '''
        if not self.is_open():
            return
        for dataset in self.data_desc.keys():
            if self._buffer[dataset]:
                to_store = np.array(self._buffer[dataset])
                new_entries = to_store.shape[0]
                curr_idx = self._write_idx[dataset]
                next_idx = curr_idx + new_entries
                if next_idx >= self.datafile[dataset].shape[0]:
                    self.datafile[dataset].resize(next_idx, axis=0)
                self.datafile[dataset][curr_idx:next_idx] = to_store
                self._buffer[dataset] = []
                self._write_idx[dataset] = next_idx
