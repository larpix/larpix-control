'''
Test serial port interface
'''

from __future__ import absolute_import
import pytest
from larpix.serialport import SerialPort, enable_logger

@pytest.mark.skip(reason='This is not a pytest file')
def test_serial_loopback(port_name='auto', enable_logging=False):
    '''Write stream of integers to serial port.  Read back and see if
    loopback data is correct.'''
    baudrate = 1000000
    timeout=0.1
    if enable_logging:
        enable_logger()
    serial_port = SerialPort(port_name)
    serial_port.baudrate = baudrate
    print(' serial baudrate:',serial_port.baudrate)
    serial_port.open()
    test_length = 256
    n_errors = 0
    max_read_length = 8192
    for iter_idx in range(10):
        write_data = range(iter_idx*10,iter_idx*10+test_length)
        write_data = [elem % 256 for elem in write_data]
        write_bits = bytearray(write_data)
        serial_port.write(write_bits)
        read_bits = b''
        read_bits += serial_port.read(max_read_length)
        print("Testing:" + str([write_bits,]))
        if str(write_bits) != str(read_bits):
            print(" Error:")
            print("  wrote: ", str(write_bits))
            print("   read: ", str(read_bits))
            print("   read_bytes / wrote_bytes: %d / %d " % (len(read_bits),
                                                             test_length))
            n_errors += 1
        else:
            print(' OK')
    serial_port.close()
    return n_errors

if '__main__' == __name__:
    test_serial_loopback()
