'''
Pick the appropriate wrapper for serial communications.

'''

def AbstractSerialPort(object):
    '''
    Specifies the interface for serial communications.

    '''

    def __init__(self, port, baudrate, timeout):
        '''
        Initialize the serial driver and prepare to read or write.

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

