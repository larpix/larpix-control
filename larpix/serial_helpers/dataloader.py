'''
A module to assist loading serial data logs for debugging
'''
from __future__ import absolute_import
import os

from .dataformatter import DataFormatter

class DataLoader(object):
    '''Simple low-level serial data log file loader'''
    def __init__(self, filename=None):
        '''Constructor'''
        self.filename = filename
        self.formatter = None
        self.bytes_read = 0
        self.file = None
        self._initialize()
        
    def _initialize(self):
        '''Initialize log for reading'''
        if not os.path.isfile(self.filename):
            raise ValueError('File does not exist: "%s"' % self.filename)
        # Set preliminary formatter
        self.formatter = DataFormatter
        # Open file
        self.open()
        # First block: file header, with data version
        byte_chunk = self.read_chunk()
        header_type = self.formatter.header_type(byte_chunk)
        if header_type != 'file':
            raise ValueError('First block in "%s" is not a file header!' %
                             self.filename)
        (major_version, minor_version) = self.formatter.data_version(
            byte_chunk)
        # Set formatter to correct version
        self.formatter = self.formatter.get_formatter_by_version(
            major_version,minor_version)
        self.close()
        return

    def read_chunk(self, n_chunks=1):
        '''Read one chunk from file stream'''
        if not self.is_open():
            # Open file if not yet opened
            self.open()
        raw_chunk = self.file.read(self.formatter.chunk_size * n_chunks)
        if len(raw_chunk) == 0:
            print('%%%%%%%%%%%% Reached end of log %%%%%%%%%%%%')
            return None
        if len(raw_chunk) < self.formatter.chunk_size:
            print('Warning: file is incorrectly truncated')
            return None
        data_chunk = bytearray(raw_chunk)
        self.bytes_read += len(data_chunk)
        return data_chunk

    def next_block_bytes(self):
        '''Load and return next serial data block as bytes'''
        head_chunk = self.read_chunk()
        if head_chunk is None:
            return None
        head_size = self.formatter.header_size(head_chunk)
        # If header size greater than 1, read rest of header
        if head_size > 1:
            head_chunk += self.read_chunk(n_chunks=(head_size-1))
        # Determine block size, and read rest of block if needed
        block_size = self.formatter.block_size(head_chunk)
        block_chunk = head_chunk[:]
        if block_size > head_size:
            block_chunk += self.read_chunk(block_size - head_size)
        if self.formatter.data_continued(block_chunk):
            # Catch continued blocks, and append data
            block_chunk += self.next_block_bytes()
        return block_chunk

    def open(self):
        '''Open the log file'''
        if self.is_open(): return
        self.file = open(self.filename,'rb')
        # Check file open format
        byte_chunk = self.file.read(len(self.formatter.file_open_chunk()))
        if not self.formatter.valid_endian(byte_chunk):
            raise ValueError('Incorrect endian word:',byte_chunk)
        return

    def is_open(self):
        '''Check if log file is open'''
        if self.file is None: return False
        return not self.file.closed
    
    def next_block(self):
        '''Load and return next serial data block'''
        # Read bytes
        block_bytes = self.next_block_bytes()
        # Catch end of data
        if block_bytes is None:
            return None
        # Parse block
        block_desc = self.formatter.parse_block(block_bytes)
        # Return
        return block_desc
    
    def close(self):
        '''Close the log file'''
        self.file.close()
        self.file = None
        return

def print_log(filename):
    '''Print (to terminal) the data blocks from a serial log file'''
    if not os.path.isfile(filename):
        print("Error: File does not exist: '%s'" % filename)
    loader = DataLoader(filename)
    while True:
        block = loader.next_block()
        if block is None: break
        print('%%%%%%%%%%%%%%%%')
        print('  Block type:',block['block_type'])
        if block['block_type']=='file':
            print(block)
        if block['block_type']=='data':
            print('  Data type:  ',block['data_type'])
            print('  Size:       ',len(block['data']))
            if len(block['data'])>10:
                print('  Start bytes:',block['data'][:10])
                print('  End bytes:  ',block['data'][-10:])
            else:
                print('  Bytes:      ',block['data'])
    return
