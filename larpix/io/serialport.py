'''
The serial port IO interface.

'''
from __future__ import absolute_import
import time
import os
import platform
import warnings

from larpix.io import IO
from larpix.larpix import Packet

warnings.simplefilter('default', DeprecationWarning)
warnings.warn('The serialport module is deprecated and will be removed '
        'in larpix-control v3.0.0.', DeprecationWarning)

class SerialPort(IO):
    '''Wrapper for various serial port interfaces across platforms.

       Automatically loads correct driver based on the supplied port
       name:

           - ``'/dev/anything'`` ==> Linux ==> pySerial
           - ``'scan-ftdi'`` ==> MacOS ==> libFTDI

    '''
    # Guesses for default port name by platform
    _default_port_map = {
        'Default':['/dev/ttyUSB2','/dev/ttyUSB1'], # Same as Linux
        'Linux':['/dev/serial0', '/dev/ttyAMA0', '/dev/ttyUSB2','/dev/ttyUSB1',
        '/dev/ttyUSB0'],   # Linux
        'Darwin':['scan-ftdi',],     # OS X
    }
    _logger = None
    start_byte = b'\x73'
    stop_byte = b'\x71'
    max_write = 250
    fpga_packet_size = 10
    def __init__(self, port=None, baudrate=1000000, timeout=0):
        super(SerialPort, self).__init__()
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
        self.logger = None
        if not (self._logger is None):
            self.logger = self._logger
        return

    @staticmethod
    def _format_UART(packet):
        packet_bytes = packet.bytes()
        daisy_chain_byte = b'\x00'
        formatted_packet = (SerialPort.start_byte + packet_bytes +
                daisy_chain_byte + SerialPort.stop_byte)
        return formatted_packet

    @staticmethod
    def _parse_input(bytestream):
        packet_size = SerialPort.fpga_packet_size
        start_byte = SerialPort.start_byte[0]
        stop_byte = SerialPort.stop_byte[0]
        metadata_byte_index = 8
        data_bytes = slice(1,8)
        # parse the bytestream into Packets + metadata
        byte_packets = []
        skip_slices = []
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
                index += packet_size
            else:
                # Throw out everything between here and the next start byte.
                # Note: start searching after byte 0 in case it's
                # already a start byte
                index = bytestream.find(start_byte, index+1)
                if index == -1:
                    index = bytestream_len
        return byte_packets

    @staticmethod
    def format_bytestream(formatted_packets):
        bytestreams = []
        current_bytestream = bytes()
        for packet in formatted_packets:
            if len(current_bytestream) + len(packet) <= SerialPort.max_write:
                current_bytestream += packet
            else:
                bytestreams.append(current_bytestream)
                current_bytestream = bytes()
                current_bytestream += packet
        bytestreams.append(current_bytestream)
        return bytestreams

    @classmethod
    def encode(cls, packets):
        '''
        Encodes a list of packets into a list of bytestream messages
        '''
        return [SerialPort._format_UART(packet) for packet in packets]

    @classmethod
    def decode(cls, msgs):
        '''
        Decodes a list of serial port bytestreams to packets
        '''
        packets = []
        byte_packet_list = [SerialPort._parse_input(msg) for msg in msgs]
        for packet_list in byte_packet_list:
            packets += packet_list
        for packet in packets:
            packet.chip_key = cls.generate_chip_key(chip_id=packet.chipid, io_chain=0)
        return packets

    @classmethod
    def is_valid_chip_key(cls, key):
        '''
        Valid chip keys must be strings formatted as:
        ``'<io_chain>-<chip_id>'``

        '''
        if not super(cls, cls).is_valid_chip_key(key):
            return False
        if not isinstance(key, str):
            return False
        parsed_key = key.split('-')
        if not len(parsed_key) == 2:
            return False
        try:
            _ = int(parsed_key[0])
            _ = int(parsed_key[1])
        except ValueError:
            return False
        return True

    @classmethod
    def parse_chip_key(cls, key):
        '''
        Decodes a chip key into ``'chip_id'`` and ``io_chain``

        :returns: ``dict`` with keys ``('chip_id', 'io_chain')``
        '''
        return_dict = super(cls, cls).parse_chip_key(key)
        parsed_key = key.split('-')
        return_dict['chip_id'] = int(parsed_key[1])
        return_dict['io_chain'] = int(parsed_key[0])
        return return_dict

    @classmethod
    def generate_chip_key(cls, **kwargs):
        '''
        Generates a valid ``SerialPort`` chip key

        :param chip_id: ``int`` corresponding to internal chip id

        :param io_chain: ``int`` corresponding to daisy chain number

        '''
        req_fields = ('chip_id', 'io_chain')
        if not all([key in kwargs for key in req_fields]):
            raise ValueError('Missing fields required to generate chip id'
                ', requires {}, received {}'.format(req_fields, kwargs.keys()))
        return '{io_chain}-{chip_id}'.format(**kwargs)

    def send(self, packets):
        '''
        Format the packets as a bytestream and send it to the FPGA and on
        to the LArPix ASICs.

        '''
        packet_bytes = self.encode(packets)
        bytestreams = self.format_bytestream(packet_bytes)
        for bytestream in bytestreams:
            self._write(bytestream)

    def start_listening(self):
        '''
        Start listening for incoming LArPix data by opening the serial
        port.

        '''
        super(SerialPort, self).start_listening()
        self._open()

    def stop_listening(self):
        '''
        Stop listening for LArPix data by closing the serial port.

        '''
        super(SerialPort, self).stop_listening()
        self._close()

    def empty_queue(self):
        '''
        Empty the incoming data buffer and return ``(packets,
        bytestream)``.

        '''
        data_in = b''
        keep_reading = True
        while keep_reading:
            new_data = self._read(self.max_write)
            data_in += new_data
            keep_reading = (len(new_data) == self.max_write)
        packets = self.decode([data_in])
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
        else:
            raise ValueError('Port type must be either pyserial, pylibftdi, or test')
        return

    def _resolve_port_name(self):
        '''Resolve the serial port name, based on user request'''
        if self.port is None:
            # Must set port
            raise ValueError('You must choose a serial port for operation')
        if self.port is 'auto':
            # Try to guess the correct port
            return self._guess_port()
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
        raise ValueError('Unknown port: %s' % self.port)

    def _open(self):
        '''Open the port'''
        self._ready_port()
        return

    def _close(self):
        '''Close the port'''
        if self.serial_com is None: return
        self.serial_com.close()

    def _write(self, data):
        '''Write data to serial port'''
        self._ready_port()
        write_time = time.time()
        self.serial_com.write(data)
        if not self.is_listening:
            self._close()
        if self.logger:
            self.logger.record({'data_type':'write','data':data,'time':write_time})
        return

    def _read(self, nbytes):
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
        from larpix.serial_helpers.datalogger import DataLogger
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

def _test_serial_loopback(port_name='auto', enable_logging=False):
    '''Write stream of integers to serial port.  Read back and see if
    loopback data is correct.'''
    baudrate = 1000000
    timeout=0.1
    if enable_logging:
        enable_logger()
    serial_port = SerialPort(port_name)
    serial_port.baudrate = baudrate
    print(' serial baudrate:',serial_port.baudrate)
    serial_port._open()
    test_length = 256
    n_errors = 0
    max_read_length = 8192
    for iter_idx in range(10):
        write_data = range(iter_idx*10,iter_idx*10+test_length)
        write_data = [elem % 256 for elem in write_data]
        write_bits = bytearray(write_data)
        serial_port._write(write_bits)
        read_bits = b''
        read_bits += serial_port._read(max_read_length)
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
    serial_port._close()
    return n_errors

if '__main__' == __name__:
    _test_serial_loopback()

