'''
A module for serial data formatting and parsing
'''
from __future__ import absolute_import
import struct

class DataFormatter(object):
    '''Abstract base class for serial data reader/writer'''
    data_version_major = 0
    data_version_minor = 0
    chunk_size = 8 # simplify life by writing in 8 byte words
    endian_test_word = bytearray(b'\x01\x02\x03\x04\x05\x06\x07\x08')
    header_type_by_desc = {'file': int('0001',2),
                           'data': int('0010',2)}
    header_size_by_desc = {'file': 2} # in chunks
    header_type_mask = int('00001111',2)

    @classmethod
    def file_open_chunk(cls):
        '''First chunk in file, to confirm file format is correct'''
        return cls.endian_test_word

    @classmethod
    def number_of_chunks(cls,n_bytes):
        '''Determine number of chunks needed for the given number of bytes'''
        n_chunks = int(n_bytes / cls.chunk_size)
        if (n_bytes % cls.chunk_size) != 0:
            n_chunks += 1  # must pad to catch remaining bytes
        return n_chunks

    @classmethod
    def header_type(cls,header_chunk):
        '''Return the header type, given the first header chunk'''
        header_bits = cls.header_type_mask & header_chunk[0]
        for (key, val) in cls.header_type_by_desc.items():
            if val == header_bits:
                return key
        raise ValueError('Undefined header type:', header_bits)

    @classmethod
    def header_size(cls,header_chunk):
        '''Return the total header size in chunks, given the first chunk'''
        head_type = cls.header_type(header_chunk)
        return cls.header_size_by_desc[head_type]

    @classmethod
    def block_size(cls,header_chunk):
        '''Return the total block size in chunks, given the header chunks'''
        # For base class, only the file header
        return cls.header_size(header_chunk)

    @classmethod
    def data_continued(cls,block_chunk):
        '''Return true if block data is continued in next block'''
        return False

    @classmethod
    def data_version(cls,header_chunk):
        '''Return the data version, given the first file header chunk'''
        return (header_chunk[2],header_chunk[3])


    @classmethod
    def format_file_header(cls, file_head_desc):
        '''Generate a file header'''
        bytes = bytearray([cls.header_type_by_desc['file'], 0,
                           cls.data_version_major, cls.data_version_minor,
                           0,0,0,0])
        return bytes

    @classmethod
    def parse_file_header(cls, file_head_bytes):
        '''Parse a file header'''
        if not (cls.header_type(file_head_bytes) is 'file'):
            raise ValueError('Not a file header')
        file_head_desc = {}
        file_head_desc['block_type'] = 'file'
        (major_version, minor_version) = cls.data_version(file_head_bytes)
        file_head_desc['major_version'] = major_version
        file_head_desc['minor_version'] = minor_version
        return file_head_desc

    @classmethod
    def format_data_block(cls, data_block_desc):
        '''Generate a data block'''
        raise NotImplementedError

    @classmethod
    def parse_data_block(cls, data_block_bytes):
        '''Parse a data block'''
        raise NotImplementedError

    @classmethod
    def get_formatter_by_version(cls, major_version, minor_version):
        '''Find the correct formatter, given a data version'''
        for formatter in DataFormatter.get_all_formatters():
            if (formatter.data_version_major==major_version
                and formatter.data_version_minor==minor_version):
                return formatter()
        raise ValueError('No parser found for data version %d-%d' %
                         (data_major_version,data_minor_version))

    @classmethod
    def get_all_formatters(cls):
        '''Find all formatters, based on class inheritance'''
        formatters = [cls,] + cls.__subclasses__()
        for scls in cls.__subclasses__():
            formatters += scls.__subclasses__()
        return formatters

    @classmethod
    def valid_endian(cls, bytes):
        '''Check bytes to determine if it is the correct endian word'''
        return (bytes == cls.endian_test_word)

    @classmethod
    def format_block(cls, block_desc):
        '''Check block type and delegate to correct formatter'''
        if block_desc['block_type'] is 'file':
            return cls.format_file_header(block_desc)
        raise ValueError('Undefined block type:', block_desc['block_type'])

    @classmethod
    def parse_block(cls, block):
        '''Check block type and delegate to correct parser'''
        if cls.header_type(block) is 'file':
            return cls.parse_file_header(block)
        raise ValueError('Undefined header type:', header_bits)



class DataFormatter_v1_0(DataFormatter):
    '''Explicit data formatter for data version 1.0'''
    data_version_major = 1
    data_version_minor = 0
    data_type_by_desc = {'read': int('01',2),
                         'write': int('10',2),
                         'message': int('11',2)}
    data_desc_by_type = dict([(val,key) for (key,val) in
                              data_type_by_desc.items()])
    data_type_mask = int('00110000',2)
    data_final_flag = 0
    data_continued_flag = 1
    data_continued_mask = int('01000000',2)
    header_size_by_desc = {'file':2,
                           'data':2} # in chunks
    data_block_max_bytes = int('1'*16,2)  # 65 kbytes

    @classmethod
    def data_continued(cls,block_chunk):
        '''Return true if block data is continued in next block'''
        if cls.header_type(block_chunk) is 'data':
            is_cont = (block_chunk[0] & cls.data_continued_mask)>>6
            return (is_cont == cls.data_continued_flag)
        return False

    @classmethod
    def block_size(cls,header_chunk):
        '''Return the total block size in chunks, given the header chunks'''
        if cls.header_type(header_chunk) == 'file':
            # File header has no data payload
            return cls.header_size(header_chunk)
        elif cls.header_type(header_chunk) == 'data':
            return cls.data_block_size(header_chunk)
        raise ValueError('Cannot determine size of unknown block type')

    @classmethod
    def data_block_size(cls,data_header_chunk):
        '''Return the total block size in chunks, given the header chunks'''
        data_size = struct.unpack('<I',data_header_chunk[4:8])[0]
        return (cls.header_size_by_desc['data']
                + cls.number_of_chunks(data_size))

    @classmethod
    def format_file_header(cls, file_head_desc):
        '''Generate a file header'''
        bytes = bytearray([cls.header_type_by_desc['file'], 0,
                           cls.data_version_major, cls.data_version_minor,
                           0,0,0,0])
        bytes += struct.pack("<Q", int(file_head_desc['starttime']*1e6))
        return bytes

    @classmethod
    def parse_file_header(cls, file_head_bytes):
        '''Parse a file header'''
        file_head_desc = DataFormatter.parse_file_header(file_head_bytes)
        stime = (struct.unpack("<Q",file_head_bytes[8:16])[0]) * 1.0e-6
        file_head_desc['starttime'] = stime
        return file_head_desc

    @classmethod
    def format_data_block(cls, data_block_desc):
        '''Generate a data block'''
        bytes = bytearray()
        header_type = cls.header_type_by_desc['data']
        data_type = cls.data_type_by_desc[data_block_desc['data_type']]
        data = data_block_desc['data']
        n_data_bytes = len(data)
        while n_data_bytes >= 0:
            current_data = data
            cur_data_bytes = n_data_bytes
            if cur_data_bytes > cls.data_block_max_bytes:
                # Chop extra large blocks into smaller blocks
                current_data = data[:cls.data_block_max_bytes]
                data = data[cls.data_block_max_bytes:]
                cur_data_bytes = cls.data_block_max_bytes
                data_head_byte_0 = (header_type
                                    | (data_type << 4)
                                    | (cls.data_continued_flag << 6))
                n_data_bytes = len(data)
            else:
                # Process final block
                data = []
                n_data_bytes = -1 # Set to negative to exit loop
                # Mark as last data block
                data_head_byte_0 = (header_type
                                    | (data_type << 4)
                                    | (cls.data_final_flag << 6))
            bytes += (bytearray([data_head_byte_0, 0, 0, 0])
                      + struct.pack("<I", cur_data_bytes))
            bytes += struct.pack("<Q", int(data_block_desc['time']*1e6))
            if cur_data_bytes > 0:
                bytes += bytearray(current_data)
        data_chunks = cls.number_of_chunks(len(bytes))
        n_pad_bytes = (data_chunks * cls.chunk_size) - len(bytes)
        if n_pad_bytes > 0:
            # Pad block to fill chunk_size
            bytes += bytearray([0]*n_pad_bytes)
        return bytes

    @classmethod
    def parse_data_block(cls, data_block):
        '''Parse a data block'''
        data_block_desc = {}
        if not (cls.header_type(data_block) is 'data'):
            raise ValueError('Not a data block')
        data_block_desc['block_type'] = 'data'
        data_type_flag = (data_block[0] & cls.data_type_mask) >> 4
        data_block_desc['data_type'] = cls.data_desc_by_type[data_type_flag]
        head_size = cls.header_size_by_desc['data']
        head_bytes = head_size * cls.chunk_size
        data_len = struct.unpack('<I',data_block[4:8])[0]
        dattime = (struct.unpack("<Q",data_block[8:16])[0]) * 1.0e-6
        data_block_desc['time'] = dattime
        data_block_desc['data'] = data_block[head_bytes:head_bytes+data_len]
        if cls.data_continued(data_block):
            # Catch data from additional blocks, and append
            data_len_chunks = cls.number_of_chunks(data_len)
            next_block = (head_size + data_len_chunks)*cls.chunk_size
            cont_data_desc = cls.parse_data_block(data_block[next_block:])
            data_block_desc['data'] += cont_data_desc['data']
        return data_block_desc

    @classmethod
    def format_block(cls, block_desc):
        '''Check block type and delegate to correct formatter'''
        if block_desc['block_type'] is 'file':
            return cls.format_file_header(block_desc)
        elif block_desc['block_type'] is 'data':
            return cls.format_data_block(block_desc)
        raise ValueError('Undefined block type:', block_desc['block_type'])

    @classmethod
    def parse_block(cls, block):
        '''Check block type and delegate to correct parser'''
        if cls.header_type(block) is 'file':
            return cls.parse_file_header(block)
        elif cls.header_type(block) is 'data':
            return cls.parse_data_block(block)
        raise ValueError('Undefined header type:', header_bits)



# Define current default formatter
default_formatter = DataFormatter_v1_0
