'''
A module to assist serial data logging and debugging
'''
from __future__ import absolute_import
import os, time, atexit

from .dataformatter import default_formatter

class DataLogger(object):
    '''Simple low-level serial data logger for debugging purposes'''

    def __init__(self, filename=None, formatter=default_formatter):
        '''Constructor'''
        self.starttime = time.time() # Time since epoch
        if filename is None:
            # Prepare default log path
            logpath = self._default_logpath()
            self.filename = os.path.join(logpath, self._default_logname())
        else:
            # Use provided log file name
            self.filename = filename
        self.formatter = formatter
        self.bytes_written = 0
        self.buffer = bytearray()
        self._buffer_flush = 32000 # flush at 32000 byte buffer size
        self._log_initialized = False
        # Has log been initialized?
        if not self._log_initialized:
            self._initialize_log()
        # Enable, and ensure buffer flushed on python exit
        self._is_enabled = True
        self._exit_func = atexit.register(self.flush)
        
    def _default_logname(self):
        '''Generate a log file name'''
        log_prefix = 'datalog'
        log_specifier = time.strftime('%Y_%m_%d_%H_%M_%S_%Z')
        log_postfix = '.dat'
        return (log_prefix + '_' + log_specifier + '_' + log_postfix)

    def _default_logpath(self):
        '''Generate a log file path'''
        return os.path.join(os.getenv('LP_DATALOG_DIR',os.getcwd()),'datalog')
    
    def _make_file_header(self):
        '''Generate a file header bytearray'''
        return self.formatter.format_block({'block_type':'file',
                                            'starttime':self.starttime})

    def _initialize_log(self):
        '''Initialize log for first write'''
        # Prepend file format test
        self.buffer += self.formatter.file_open_chunk()
        # Prepend file header
        self.buffer += self._make_file_header()
        # Create path, if needed
        logpath = os.path.dirname(self.filename)
        if not os.path.exists(logpath):
            os.makedirs(logpath)
        self._log_initialized = True
        return
        
    def record(self,data_block_desc):
        '''Log a data block'''
        if not self._is_enabled: return
        data_block_desc['block_type'] = 'data'
        #data_block_desc['time'] = time.time()
        self.buffer += self.formatter.format_block(data_block_desc)
        if len(self.buffer) > self._buffer_flush:
            # Flush current data to file
            self.flush()
        return

    def flush(self):
        '''Write current data blocks to file'''
        # Check if enabled
        if not self._is_enabled: return
        # Is there data to log?
        if len(self.buffer) == 0: return  # No data
        # Write data to file
        with open(self.filename,'ab') as log_file:
            log_file.write(self.buffer)
        # Track total bytes written
        self.bytes_written += len(self.buffer)
        # Clear buffer
        self.buffer = bytearray()
        return

    def enable(self):
        '''Enable logger'''
        self._is_enabled = True
        return
    
    def disable(self):
        '''Flush logger and disable'''
        self.flush()
        self._is_enabled = False
        return

    def is_enabled(self):
        '''Return true if logger is enabled'''
        return self._is_enabled
