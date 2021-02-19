'''
The serial port IO interface.

'''
from __future__ import absolute_import
import time
import os
import platform
import warnings

from larpix.io import IO
from larpix import Packet
import larpix.bitarrayhelper as bah

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
    hwm = 10000 # max bytes to read from an empty queue

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
        self.leftover_bytes = b''
        if not (self._logger is None):
            self.logger = self._logger
        return

    @staticmethod
    def _format_UART(packet):
        packet_bytes = packet.bytes()
        formatted_packet = (SerialPort.start_byte + packet_bytes +
                SerialPort.stop_byte)
        return formatted_packet

    @staticmethod
    def _parse_input(bytestream, leftover_bytes=b''):
        packet_size = SerialPort.fpga_packet_size
        start_byte = SerialPort.start_byte[0]
        stop_byte = SerialPort.stop_byte[0]
        data_bytes = slice(1,9)
        # parse the bytestream into Packets
        byte_packets = []
        skip_slices = []
        bytestream = leftover_bytes + bytestream
        bytestream_len = len(bytestream)
        last_possible_start = bytestream_len - packet_size
        index = 0
        while index <= last_possible_start:
            if (bytestream[index] == start_byte and
                    bytestream[index+packet_size-1] == stop_byte):
                byte_packets.append(Packet(bytestream[index+1:index+9]))
                index += packet_size
            else:
                # Throw out everything between here and the next start byte.
                # Note: start searching after byte 0 in case it's
                # already a start byte
                index = bytestream.find(start_byte, index+1)
                if index == -1:
                    index = bytestream_len
        if index <= bytestream_len:
            leftover_bytes = bytestream[index:]
        return byte_packets, leftover_bytes

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
    def decode(cls, msgs, leftover_bytes=b''):
        '''
        Decodes a list of serial port bytestreams to packets
        '''
        packets = []
        byte_packet_list = [None] * len(msgs)
        for i in range(len(msgs)):
            byte_packet_list[i], leftover_bytes = SerialPort._parse_input(msgs[i], leftover_bytes)
        for packet_list in byte_packet_list:
            packets += packet_list
        for packet in packets:
            packet.io_channel = 1
            packet.io_group = 1
        return packets, leftover_bytes

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
        count = 0
        while keep_reading:
            new_data = self._read(self.max_write)
            data_in += new_data
            count = len(data_in)
            keep_reading = (len(new_data) == self.max_write and count < self.hwm)
        packets, self.leftover_bytes = self.decode([data_in], leftover_bytes=self.leftover_bytes)
        return (packets, data_in)

    def set_larpix_uart_clk_ratio(self, value):
        '''
        Sends a special command to modify the larpix uart clk ratio (how many
        clock cycles correspond to one bit). A value of 2 means 1 uart bit == 2
        clk cycles

        '''
        data_out = (
            b'c' # start byte
            + b'\x00' # address
            + bah.fromuint(value, 8, endian='big').tobytes()
            + b'\x00'*6 # unused
            + b'q' # stop byte
            )
        self._write(data_out)

    def set_larpix_reset_cnt(self, value):
        '''
        Sends a special command to modify the length of the reset signal
        sent to the larpix chips. The reset will be held low for value + 1
        larpix clk rising edges

        '''
        data_out = (
            b'c' # start byte
            + b'\x01' # address
            + bah.fromuint(value, 8, endian='big').tobytes()
            + b'\x00'*6 # unused
            + b'q' # stop byte
            )
        self._write(data_out)

    def larpix_reset(self):
        '''
        Sends a special command to issue a larpix reset pulse. Pulse length
        is set by set_larpix_reset_cnt().

        '''
        data_out = (
            b'c' # start byte
            + b'\x02' # address
            + b'\x00'*7 # unused
            + b'q' # stop byte
            )
        self._write(data_out)

    def set_utility_pulse(self, pulse_len=None, pulse_rep=None):
        '''
        Sends a special command to issue set up utility pulser. Pulse length
        is the number of larpix clk cyles pulse is high, and pulse rep is the
        number of clk cycles until the next pulse.

        '''
        data_out = b''
        if not pulse_len is None:
            data_out += (
                b'c' # start byte
                + b'\x03' # address
                + bah.fromuint(max(pulse_len-2,0), 32, endian='big').tobytes()[::-1] # -2 for proper register value -> clk cycles conv.
                + b'\x00'*3 # unused
                + b'q' # stop byte
                )
        if not pulse_rep is None:
            data_out += (
                b'c' # start byte
                + b'\x04' # address
                + bah.fromuint(max(pulse_rep-1,0), 32, endian='big').tobytes()[::-1] # -1 for proper register value -> clk cycles conv.
                + b'\x00'*3 # unused
                + b'q' # stop byte
                )
        if data_out:
            self._write(data_out)
        else:
            raise RuntimeError('set either or both of pulse_len and pulse_rep')

    def enable_utility_pulse(self):
        '''
        Sends a special command to enable the utility pulser. Pulse
        characteristics can be set by set_utility_pulse().

        '''
        data_out = (
            b'c' # start byte
            + b'\x05' # address
            + b'\x01' # enable
            + b'\x00'*6 # unused
            + b'q' # stop byte
            )
        self._write(data_out)

    def disable_utility_pulse(self):
        '''
        Sends a special command to disable the utility pulser. Pulse
        characteristics can be set by set_utility_pulse().

        '''
        data_out = (
            b'c' # start byte
            + b'\x05' # address
            + b'\x00' # disable
            + b'\x00'*6 # unused
            + b'q' # stop byte
            )
        self._write(data_out)

    def reset(self):
        '''
        Sends a special command to reset FPGA and larpix.

        '''
        data_out = (
            b'c' # start byte
            + b'\x06' # address
            + b'\x00'*7 # unused
            + b'q' # stop byte
            )
        self._write(data_out)

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
        if self.port_type == 'pyserial':
            self._ready_port = self._ready_port_pyserial
            import serial
            self.serial_com = serial.Serial(self.resolved_port,
                                            baudrate=self.baudrate,
                                            timeout=self.timeout)
        elif self.port_type == 'pylibftdi':
            self._ready_port = self._ready_port_pylibftdi
            import pylibftdi
            self.serial_com = pylibftdi.Device(self.resolved_port)
        elif self.port_type == 'test':
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
        if self.port == 'auto':
            # Try to guess the correct port
            return self._guess_port()
        return self.port

    def _resolve_port_type(self):
        '''Resolve the type of serial port, based on the name'''
        if isinstance(self.resolved_port, str):
            if self.resolved_port.startswith('/dev'):
                # Looks like a tty device.  Use pyserial.
                return 'pyserial'
            elif self.resolved_port == 'test':
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

