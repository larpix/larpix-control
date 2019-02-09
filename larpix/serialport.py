'''
The serial port IO interface.

'''
from __future__ import absolute_import
import time
import os
import platform
from larpix.larpix import (Configuration, Packet)

class SerialPort(object):
    '''Wrapper for various serial port interfaces across platforms.

       Automatically loads correct driver based on the supplied port
       name:

           - ``'/dev/anything'`` ==> Linux ==> pySerial
           - ``'scan-ftdi'`` ==> MacOS ==> libFTDI
           - ``('zmq', push_address, pull_address)`` ==> ZeroMQ
    '''
    # Guesses for default port name by platform
    _default_port_map = {
        'Default':['/dev/ttyUSB2','/dev/ttyUSB1'], # Same as Linux
        'Linux':['/dev/ttyAMA0', '/dev/ttyUSB2','/dev/ttyUSB1',
        '/dev/ttyUSB0'],   # Linux
        'Darwin':['scan-ftdi',],     # OS X
    }
    _logger = None
    start_byte = b'\x73'
    stop_byte = b'\x71'
    max_write = 250
    def __init__(self, port=None, baudrate=9600, timeout=0):
        if port is None:
            port = self._guess_port()
        self.port = port
        self.resolved_port = ''
        self.port_type = ''
        self.baudrate = baudrate
        self.timeout = timeout
        self.max_write = 250
        self.serial_com = None
        self._initialize_serial_com()
        self.is_listening = False
        self.logger = None
        if not (self._logger is None):
            self.logger = self._logger
        return

    @staticmethod
    def format_UART(packet):
        packet_bytes = packet.bytes()
        daisy_chain_byte = b'\x00'
        formatted_packet = (SerialPort.start_byte + packet_bytes +
                daisy_chain_byte + SerialPort.stop_byte)
        return formatted_packet

    @staticmethod
    def parse_input(bytestream):
        packet_size = Configuration.fpga_packet_size  #vb
        start_byte = SerialPort.start_byte[0]
        stop_byte = SerialPort.stop_byte[0]
        metadata_byte_index = 8
        data_bytes = slice(1,8)
        # parse the bytestream into Packets + metadata
        byte_packets = []
        skip_slices = []
        #current_stream = bytestream
        bytestream_len = len(bytestream)
        last_possible_start = bytestream_len - packet_size
        index = 0
        while index <= last_possible_start:
            if (bytestream[index] == start_byte and
                    bytestream[index+packet_size-1] == stop_byte):
                '''
                metadata = current_stream[metadata_byte_index]
                # This is necessary because of differences between
                # Python 2 and Python 3
                if isinstance(metadata, int):  # Python 3
                    code = 'uint:8='
                elif isinstance(metadata, str):  # Python 2
                    code = 'bytes:1='
                byte_packets.append((Bits(code + str(metadata)),
                    Packet(current_stream[data_bytes])))
                '''
                byte_packets.append(Packet(bytestream[index+1:index+8]))
                #current_stream = current_stream[packet_size:]
                index += packet_size
            else:
                # Throw out everything between here and the next start byte.
                # Note: start searching after byte 0 in case it's
                # already a start byte
                index = bytestream.find(start_byte, index+1)
                if index == -1:
                    index = bytestream_len
                #if next_start_index != 0:
                #        print('Warning: %d extra bytes in data stream!' %
                #        (next_start_index+1))
                #current_stream = current_stream[1:][next_start_index:]
        #if len(current_stream) != 0:
        #    print('Warning: %d extra bytes at end of data stream!' %
        #          len(current_stream))
        return byte_packets

    @staticmethod
    def format_bytestream(formatted_packets):
        bytestreams = []
        current_bytestream = bytes()
        for packet in formatted_packets:
            if len(current_bytestream) + len(packet) <= SerialPort.max_write:  #vb
                current_bytestream += packet
            else:
                bytestreams.append(current_bytestream)
                current_bytestream = bytes()
                current_bytestream += packet
        bytestreams.append(current_bytestream)
        return bytestreams

    def send(self, packets):
        '''
        Format the packets as a bytestream and send it to the FPGA and on
        to the LArPix ASICs.

        '''
        packet_bytes = [self.format_UART(p) for p in packets]
        bytestreams = self.format_bytestream(packet_bytes)
        for bytestream in bytestreams:
            self.write(bytestream)

    def start_listening(self):
        self.open()
        self.is_listening = True

    def stop_listening(self, read):
        if read:
            data = self.empty_queue()
        else:
            data = None
        self.close()
        self.is_listening = False
        return data

    def empty_queue(self):
        data_in = b''
        keep_reading = True
        while keep_reading:
            new_data = self.read(self.max_write)
            data_in += new_data
            keep_reading = (len(new_data) == self.max_write)
        packets = self.parse_input(data_in)
        return (packets, data_in)

    @classmethod
    def _guess_port(cls):
        '''Guess at correct port name based on platform'''
        platform_default = 'Default'
        platform_name = platform.system()
        if platform_name not in cls._default_port_map:
            platform_name = platform_default
        default_devs = cls._default_port_map[platform_name]
        osx_cmd = 'system_profiler SPUSBDataType | grep -C 7 FTDI | grep Serial'
        for default_dev in default_devs:
            if default_dev.startswith('/dev'): # pyserial
                try:
                    if os.stat(default_dev):
                        return default_dev
                except OSError:
                    continue
            elif default_dev == 'scan-ftdi':
                if platform_name == 'Darwin':  # scan for pylibftdi on OS X
                    # Scan for FTDI devices
                    result = os.popen(osx_cmd).read()
                    if len(result) > 0:
                        idx = result.find('Serial Number:')
                        dev_name = result[idx+14:idx+24].strip()
                        print('Autoscan found FTDI device: "%s"' % dev_name)
                        return dev_name
            elif not default_dev.startswith('/dev'):  # assume pylibftdi
                return default_dev
        raise OSError('Cannot find serial device for platform: %s' %
                      platform_name)

    def _ready_port(self):
        '''Function handle.  Will be reset to appropriate method'''
        raise NotImplementedError('Serial port type has not been defined.')

    def _ready_port_pyserial(self):
        '''Ready a pyserial port'''
        if not self.serial_com.is_open:
            # Open, if necessary
            self.serial_com.open()
        return

    def _ready_port_pylibftdi(self):
        '''Ready a pylibftdi port'''
        if self.serial_com.closed:
            # Open port
            self.serial_com.open()
        # Confirm baudrate (Required for OS X)
        self._confirm_baudrate()
        return

    def _ready_port_test(self):
        return True

    def _ready_port_zmq(self):
        return True

    def _confirm_baudrate(self):
        '''Check and set the baud rate'''
        if self.serial_com.baudrate != self.baudrate:
            # Reset baudrate
            self.serial_com.baudrate = self.baudrate
        return

    def _initialize_serial_com(self):
        '''Initialize the low-level serial com connection'''
        self.resolved_port = self._resolve_port_name()
        self.port_type = self._resolve_port_type()
        if self.port_type is 'pyserial':
            self._ready_port = self._ready_port_pyserial
            import serial
            self.serial_com = serial.Serial(self.resolved_port,
                                            baudrate=self.baudrate,
                                            timeout=self.timeout)
        elif self.port_type is 'pylibftdi':
            self._ready_port = self._ready_port_pylibftdi
            import pylibftdi
            self.serial_com = pylibftdi.Device(self.resolved_port)
        elif self.port_type is 'test':
            self._ready_port = self._ready_port_test
            import test.test_larpix as test_lib
            self.serial_com = test_lib.FakeSerialPort()
        elif self.port_type is 'zmq':
            self._ready_port = self._ready_port_zmq
            from larpix.zmqcontroller import Serial_ZMQ
            self.serial_com = Serial_ZMQ(self.port[1], self.timeout)
        else:
            raise ValueError('Port type must be either pyserial, pylibftdi, or test')
        return

    def _resolve_port_name(self):
        '''Resolve the serial port name, based on user request'''
        if self.port is None:
            # Must set port
            raise ValueError('You must choose a serial port for operation')
        # FIXME: incorporate auto-scan feature
        if self.port is 'auto':
            # Try to guess the correct port
            return self._guess_port()
        # FIXME: incorporate list option?
        #elif isinstance(self.port, list):
        #    # Try to determine best choice from list
        #    for port_name in list:
        #        if self._port_exists(port_name):
        #            return port_name
        return self.port

    def _resolve_port_type(self):
        '''Resolve the type of serial port, based on the name'''
        if isinstance(self.resolved_port, str):
            if self.resolved_port.startswith('/dev'):
                # Looks like a tty device.  Use pyserial.
                return 'pyserial'
            elif self.resolved_port is 'test':
                # Testing port. Don't use an external library
                return 'test'
            elif not self.resolved_port.startswith('/dev'):
                # Looks like a libftdi raw device.  Use pylibftdi.
                return 'pylibftdi'
        elif self.resolved_port[0] == 'zmq':
            # ZeroMQ communication
            return 'zmq'
        raise ValueError('Unknown port: %s' % self.port)

    def open(self):
        '''Open the port'''
        self._ready_port()
        return

    def close(self):
        '''Close the port'''
        if self.serial_com is None: return
        self.serial_com.close()

    def write(self, data):
        '''Write data to serial port'''
        self._ready_port()
        write_time = time.time()
        self.serial_com.write(data)
        if not self.is_listening:
            self.close()
        if self.logger:
            self.logger.record({'data_type':'write','data':data,'time':write_time})
        return

    def read(self, nbytes):
        '''Read data from serial port'''
        self._ready_port()
        read_time = time.time()
        data = self.serial_com.read(nbytes)
        if self.logger:
            self.logger.record({'data_type':'read','data':data,'time':read_time})
        return data

def enable_logger(filename=None):
    '''Enable serial data logger'''
    if SerialPort._logger is None:
        from larpix.datalogger import DataLogger
        SerialPort._logger = DataLogger(filename)
    if not SerialPort._logger.is_enabled():
        SerialPort._logger.enable()
    return

def disable_logger():
    '''Disable serial data logger'''
    if SerialPort._logger is not None:
        SerialPort._logger.disable()
    return

def flush_logger():
    '''Flush serial data logger data to output file'''
    if SerialPort._logger is not None:
        SerialPort._logger.flush()
    return

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
