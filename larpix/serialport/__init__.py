'''
Pick the appropriate wrapper for serial communications.

'''

import re
import platform
import os

def guess_port():
    '''
    Guess the particular port class to use on a particular system.

    Return a tuple of ``(serial_port_class, port_name)``, or ``None`` if
    the guess is inconclusive. If the port name cannot be imputed but
    the serial port class can be, then return
    ``(serial_port_class, None)``.

    '''
    platform_name = platform.system()
    if platform_name == 'Linux':
        return _guess_port_linux()
    elif platform_name == 'Darwin':
        return _guess_port_mac()
    else:
        return None

def _guess_port_linux():
    import larpix.serialport.linux as LinuxSerial
    SerialPort = LinuxSerial.LinuxSerialPort
    if os.path.exists('/dev/ttyUSB2'):  # Laptop
        port = '/dev/ttyUSB2'
    elif os.path.exists('/dev/ttyAMA0'):  # Raspberry Pi
        port = '/dev/ttyAMA0'
    else:
        port = None
    return (SerialPort, port)

def _guess_port_mac():
    import larpix.serialport.libftdi as libFTDISerial
    SerialPort = libFTDISerial.FTDISerialPort
    port_search = ('system_profiler SPUSBDataType | '
            'grep C 7 FTDI | grep Serial')
    port_search_result = os.popen(port_search).read()
    if len(port_search_result > 0):
        start_index = port_search_result.find('Serial Number:')
        port = port_search_result[start_index+14:start_index+24].strip()
    else:
        port = None
    return (SerialPort, port)

def AbstractSerialPort(object):
    '''
    Specifies the interface for serial communications.

    '''

    def __init__(self, port, baudrate, timeout):
        '''
        Initialize the serial driver and optionally prepare to read or write.

        Implementations may decide to open the serial port here or to
        open it using __enter__ and __exit__ (context managers).

        Usage:

        >>> serial_port = AbstractSerialPort(port, baudrate, timeout)
        >>> with serial_port as s:
        ...     s.read(10)
        ...     s.write(b'hello')

        Implementations are not guaranteed to work outside of the
        ``with...as`` context manager, so if your implementation does
        not require one, write a wrapper for it anyways (or just inherit
        from this base class).

        '''
        pass

    def __enter__(self):
        '''
        Prepare for a sequence of serial reads or writes.

        By default, this function just returns self (i.e. does nothing).

        '''
        return self

    def __exit__(self, type, value, traceback):
        '''
        Clean up after a sequence of serial reads or writes.

        By default, this function does nothing.

        '''
        pass

    def read(self, num_bytes):
        '''
        Read the specified number of bytes from the serial port.

        If the read takes longer than self.timeout, then abort early and
        return whatever bytes are there.

        '''
        pass

    def write(self, bytes_to_write):
        '''
        Write the specified bytes to the serial port.

        '''
        pass

