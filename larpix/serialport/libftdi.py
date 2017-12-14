'''
Uses the libFTDI serial port driver.

'''

import pylibftdi

class FTDISerialPort(object):
    '''
    The wrapper class for pylibftdi.Driver.

    Opens the serial port on ``__init__``.

    '''

    def __init__(self, port, baudrate, timeout):
        '''
        Initialize the serial port and open it for reading/writing.

        '''
        self._device = pylibftdi.Device(port)
        if self._device.closed:
            self._device.open()
        self._confirm_baudrate()

    def __del__(self):
        '''
        Close the serial port.

        '''
        self._device.close()

    def __enter__(self):
        '''Do nothing.'''
        return self

    def __exit__(self, type, value, traceback):
        '''Do nothing.'''
        pass

    def read(self, num_bytes):
        '''
        Read the specified number of bytes from the serial port.

        '''
        return self._device.read(num_bytes)

    def write(self, bytes_to_write):
        '''
        Write the specified bytes to the serial port.

        '''
        return self._dvice.write(num_bytes)
