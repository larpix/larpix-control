'''
A module to control the LArPix chip.

'''
from __future__ import absolute_import

import time
import serial
from bitstring import BitArray, Bits
import json
import os
import errno

import larpix.configs as configs

class Chip(object):
    '''
    Represents one LArPix chip and helps with configuration and packet
    generation.

    '''
    num_channels = 32
    def __init__(self, chip_id, io_chain):
        self.chip_id = chip_id
        self.io_chain = io_chain
        self.data_to_send = []
        self.config = Configuration()
        self.reads = []
        self.new_reads_index = 0

    def __str__(self):
        return 'Chip (id: %d, chain: %d)' % (self.chip_id, self.io_chain)

    def show_reads(self, start=0, stop=None, step=1):
        if stop is None:
            stop = len(self.reads)
        packets = []
        for read in self.reads:
            for packet in read['packets'][start:stop:step]:
                packets.append(str(packet))
        return packets

    def show_reads_bits(self, start=0, stop=None, step=1):
        if stop is None:
            stop = len(self.reads)
        packet_bits = []
        for read in self.reads:
            for packet in read['packets'][start:stop:step]:
                packet_bits.append(' '.join(packet.bits.bin[i:i+8] for i in range(0,
                        len(packet.bits.bin), 8)))
        return packet_bits

    def append_packet(self, packet):
        '''
        Adds a packet to the specified read

        '''
        read = {}
        if len(self.reads) == 0:
            # no reads yet - create a new read for packet
            read['cpu_timestamp'] = packet.cpu_timestamp
            read['read_id'] = packet.read_id
            read['config'] = self.config.get_nondefault_registers()
            read['log_message'] = ''
            read['packets'] = [packet]
            self.reads.append(read)
        else:
            read_matches = [data for data in self.reads if data['read_id'] == packet.read_id]
            if len(read_matches) == 0:
                # no reads match read id - create a new read for packet
                read['cpu_timestamp'] = packet.cpu_timestamp
                read['read_id'] = packet.read_id
                read['config'] = self.config.get_nondefault_registers()
                read['log_message'] = ''
                read['packets'] = [packet]
                self.reads.append(read)
            elif len(read_matches) != 1:
                raise ValueError('This should not happen - multiple read ids found')
            else:
                # a read exists with read id - add packet to read
                read = read_matches[0]
                read['packets'].append(packet)

    def get_configuration_packets(self, packet_type):
        conf = self.config
        packets = [Packet() for _ in range(Configuration.num_registers)]
        packet_register_data = conf.all_data()
        for i, (packet, data) in enumerate(zip(packets, packet_register_data)):
            packet.packet_type = packet_type
            packet.chipid = self.chip_id
            packet.register_address = i
            packet.register_data = data
            packet.assign_parity()
        return packets

    def export_reads(self, only_new_reads=True):
        '''
        Return a dict of the packets this Chip has received.

        If ``only_new_reads`` is ``True`` (default), then only the
        packets since the last time this method was called will be in
        the dict. Otherwise, all of the packets stored in ``self.reads``
        will be in the dict.

        '''
        data = {}
        data['chipid'] = self.chip_id
        data['io_chain'] = self.io_chain
        if only_new_reads:
            return_reads = self.reads[self.new_reads_index:]
        else:
            return_reads = self.reads
        data['data'] = []
        for read in return_reads:
            read_dict = {}
            read_dict['cpu_timestamp'] = read['cpu_timestamp']
            read_dict['read_id'] = read['read_id']
            read_dict['config'] = read['config']
            read_dict['log_message'] = read['log_message']
            read_dict['packets'] = list(map(lambda x: x.export(), read['packets']))
            data['data'].append(read_dict)
        self.new_reads_index = len(self.reads)
        return data

class Configuration(object):
    '''
    Represents the desired configuration state of a LArPix chip.

    '''
    num_registers = 63
    pixel_trim_threshold_addresses = list(range(0, 32))
    global_threshold_address = 32
    csa_gain_and_bypasses_address = 33
    csa_bypass_select_addresses = list(range(34, 38))
    csa_monitor_select_addresses = list(range(38, 42))
    csa_testpulse_enable_addresses = list(range(42, 46))
    csa_testpulse_dac_amplitude_address = 46
    test_mode_xtrig_reset_diag_address = 47
    sample_cycles_address = 48
    test_burst_length_addresses = [49, 50]
    adc_burst_length_address = 51
    channel_mask_addresses = list(range(52, 56))
    external_trigger_mask_addresses = list(range(56, 60))
    reset_cycles_addresses = [60, 61, 62]

    TEST_OFF = 0x0
    TEST_UART = 0x1
    TEST_FIFO = 0x2
    def __init__(self):
        self.register_names = ['pixel_trim_thresholds',
                               'global_threshold',
                               'csa_gain',
                               'csa_bypass',
                               'internal_bypass',
                               'csa_bypass_select',
                               'csa_monitor_select',
                               'csa_testpulse_enable',
                               'csa_testpulse_dac_amplitude',
                               'test_mode',
                               'cross_trigger_mode',
                               'periodic_reset',
                               'fifo_diagnostic',
                               'sample_cycles',
                               'test_burst_length',
                               'adc_burst_length',
                               'channel_mask',
                               'external_trigger_mask',
                               'reset_cycles']
        self.load('default.json')

    def __str__(self):
        '''
        Converts configuration to a nicely formatted json string

        '''
        d = self.to_dict()
        l = ['\"{}\": {}'.format(key,value) for key,value in d.items()]
        return '{\n    ' + ',\n    '.join(l) + '\n}'

    def get_nondefault_registers(self):
        d = {}
        default_config = Configuration()
        for register_name in self.register_names:
            if getattr(self, register_name) != getattr(default_config, register_name):
                d[register_name] = getattr(self, register_name)
        return d

    @property
    def pixel_trim_thresholds(self):
        return self._pixel_trim_thresholds

    @pixel_trim_thresholds.setter
    def pixel_trim_thresholds(self, values):
        if not type(values) == list:
            raise ValueError("pixel_trim_threshold is not list")
        if not len(values) == Chip.num_channels:
            raise ValueError("pixel_trim_threshold length is not %d" % Chip.num_channels)
        if not all(type(value) == int for value in values):
            raise ValueError("pixel_trim_threshold is not int")
        if any(value > 31 or value < 0 for value in values):
            raise ValueError("pixel_trim_threshold out of bounds")

        self._pixel_trim_thresholds = values

    @property
    def global_threshold(self):
        return self._global_threshold

    @global_threshold.setter
    def global_threshold(self, value):
        if not type(value) == int:
            raise ValueError("global_threshold is not int")
        if value > 255 or value < 0:
            raise ValueError("global_threshold out of bounds")

        self._global_threshold = value

    @property
    def csa_gain(self):
        return self._csa_gain

    @csa_gain.setter
    def csa_gain(self, value):
        if not type(value) == int:
            raise ValueError("csa_gain is not int")
        if value > 1 or value < 0:
            raise ValueError("csa_gain out of bounds")

        self._csa_gain = value

    @property
    def csa_bypass(self):
        return self._csa_bypass

    @csa_bypass.setter
    def csa_bypass(self, value):
        if not type(value) == int:
            raise ValueError("csa_bypass is not int")
        if value > 1 or value < 0:
            raise ValueError("csa_bypass out of bounds")

        self._csa_bypass = value

    @property
    def internal_bypass(self):
        return self._internal_bypass

    @internal_bypass.setter
    def internal_bypass(self, value):
        if not type(value) == int:
            raise ValueError("internal_bypass is not int")
        if value > 1 or value < 0:
            raise ValueError("internal_bypass out of bounds")

        self._internal_bypass = value

    @property
    def csa_bypass_select(self):
        return self._csa_bypass_select

    @csa_bypass_select.setter
    def csa_bypass_select(self, values):
        if not type(values) == list:
            raise ValueError("csa_bypass_select is not list")
        if not len(values) == Chip.num_channels:
            raise ValueError("csa_bypass_select length is not %d" % Chip.num_channels)
        if not all(type(value) == int for value in values):
            raise ValueError("csa_bypass_select is not int")
        if any(value > 1 or value < 0 for value in values):
            raise ValueError("csa_bypass_select out of bounds")

        self._csa_bypass_select = values

    @property
    def csa_monitor_select(self):
        return self._csa_monitor_select

    @csa_monitor_select.setter
    def csa_monitor_select(self, values):
        if not type(values) == list:
            raise ValueError("csa_monitor_select is not list")
        if not len(values) == Chip.num_channels:
            raise ValueError("csa_monitor_select length is not %d" % Chip.num_channels)
        if not all(type(value) == int for value in values):
            raise ValueError("csa_monitor_select is not int")
        if any(value > 1 or value < 0 for value in values):
            raise ValueError("csa_monitor_select out of bounds")

        self._csa_monitor_select = values

    @property
    def csa_testpulse_enable(self):
        return self._csa_testpulse_enable

    @csa_testpulse_enable.setter
    def csa_testpulse_enable(self, values):
        if not type(values) == list:
            raise ValueError("csa_testpulse_enable is not list")
        if not len(values) == Chip.num_channels:
            raise ValueError("csa_testpulse_enable length is not %d" % Chip.num_channels)
        if not all(type(value) == int for value in values):
            raise ValueError("csa_testpulse_enable is not int")
        if any(value > 1 or value < 0 for value in values):
            raise ValueError("csa_testpulse_enable out of bounds")

        self._csa_testpulse_enable = values

    @property
    def csa_testpulse_dac_amplitude(self):
        return self._csa_testpulse_dac_amplitude

    @csa_testpulse_dac_amplitude.setter
    def csa_testpulse_dac_amplitude(self, value):
        if not type(value) == int:
            raise ValueError("csa_testpulse_dac_amplitude is not int")
        if value > 255 or value < 0:
            raise ValueError("csa_testpulse_dac_amplitude out of bounds")

        self._csa_testpulse_dac_amplitude = value

    @property
    def test_mode(self):
        return self._test_mode

    @test_mode.setter
    def test_mode(self, value):
        if not type(value) == int:
            raise ValueError("test_mode is not int")
        valid_values = [Configuration.TEST_OFF, Configuration.TEST_UART,
                        Configuration.TEST_FIFO]
        if not value in valid_values:
            raise ValueError("test_mode is not valid")

        self._test_mode = value

    @property
    def cross_trigger_mode(self):
        return self._cross_trigger_mode

    @cross_trigger_mode.setter
    def cross_trigger_mode(self, value):
        if not type(value) == int:
            raise ValueError("cross_trigger_mode is not int")
        if value > 1 or value < 0:
            raise ValueError("cross_trigger_mode out of bounds")

        self._cross_trigger_mode = value

    @property
    def periodic_reset(self):
        return self._periodic_reset

    @periodic_reset.setter
    def periodic_reset(self, value):
        if not type(value) == int:
            raise ValueError("periodic_reset is not int")
        if value > 1 or value < 0:
            raise ValueError("periodic_reset out of bounds")

        self._periodic_reset = value

    @property
    def fifo_diagnostic(self):
        return self._fifo_diagnostic

    @fifo_diagnostic.setter
    def fifo_diagnostic(self, value):
        if not type(value) == int:
            raise ValueError("fifo_diagnostic is not int")
        if value > 1 or value < 0:
            raise ValueError("fifo_diagnostic out of bounds")

        self._fifo_diagnostic = value

    @property
    def sample_cycles(self):
        return self._sample_cycles

    @sample_cycles.setter
    def sample_cycles(self, value):
        if not type(value) == int:
            raise ValueError("sample_cycles is not int")
        if value > 255 or value < 0:
            raise ValueError("sample_cycles out of bounds")

        self._sample_cycles = value

    @property
    def test_burst_length(self):
        return self._test_burst_length

    @test_burst_length.setter
    def test_burst_length(self, value):
        if not type(value) == int:
            raise ValueError("test_burst_length is not int")
        if value > 65535 or value < 0:
            raise ValueError("test_burst_length out of bounds")

        self._test_burst_length = value

    @property
    def adc_burst_length(self):
        return self._adc_burst_length

    @adc_burst_length.setter
    def adc_burst_length(self, value):
        if not type(value) == int:
            raise ValueError("adc_burst_length is not int")
        if value > 255 or value < 0:
            raise ValueError("adc_burst_length out of bounds")

        self._adc_burst_length = value

    @property
    def channel_mask(self):
        return self._channel_mask

    @channel_mask.setter
    def channel_mask(self, values):
        if not type(values) == list:
            raise ValueError("channel_mask is not list")
        if not len(values) == Chip.num_channels:
            raise ValueError("channel_mask length is not %d" % Chip.num_channels)
        if not all(type(value) == int for value in values):
            raise ValueError("channel_mask is not int")
        if any(value > 1 or value < 0 for value in values):
            raise ValueError("channel_mask out of bounds")

        self._channel_mask = values

    @property
    def external_trigger_mask(self):
        return self._external_trigger_mask

    @external_trigger_mask.setter
    def external_trigger_mask(self, values):
        if not type(values) == list:
            raise ValueError("external_trigger_mask is not list")
        if not len(values) == Chip.num_channels:
            raise ValueError("external_trigger_mask length is not %d" % Chip.num_channels)
        if not all(type(value) == int for value in values):
            raise ValueError("external_trigger_mask is not int")
        if any(value > 1 or value < 0 for value in values):
            raise ValueError("external_trigger_mask out of bounds")

        self._external_trigger_mask = values

    @property
    def reset_cycles(self):
        return self._reset_cycles

    @reset_cycles.setter
    def reset_cycles(self, value):
        if not type(value) == int:
            raise ValueError("reset_cycles is not int")
        if value > 16777215 or value < 0:
            raise ValueError("reset_cycles out of bounds")

        self._reset_cycles = value

    def enable_channels(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.channel_mask[channel] = 0

    def disable_channels(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.channel_mask[channel] = 1

    def enable_normal_operation(self):
        #TODO Ask Dan what this means
        # Load configuration for a normal physics run
        pass

    def enable_external_trigger(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.external_trigger_mask[channel] = 0

    def disable_external_trigger(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.external_trigger_mask[channel] = 1

    def enable_testpulse(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.csa_testpulse_enable[channel] = 1

    def disable_testpulse(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.csa_testpulse_enable[channel] = 0

    def enable_analog_monitor(self, channel):
        self.csa_monitor_select[channel] = 1

    def disable_analog_monitor(self):
        self.csa_monitor_select = [0] * Chip.num_channels

    def all_data(self):
        bits = []
        num_channels = Chip.num_channels
        for channel in range(num_channels):
            bits.append(self.trim_threshold_data(channel))
        bits.append(self.global_threshold_data())
        bits.append(self.csa_gain_and_bypasses_data())
        for chunk in range(4):
            bits.append(self.csa_bypass_select_data(chunk))
        for chunk in range(4):
            bits.append(self.csa_monitor_select_data(chunk))
        for chunk in range(4):
            bits.append(self.csa_testpulse_enable_data(chunk))
        bits.append(self.csa_testpulse_dac_amplitude_data())
        bits.append(self.test_mode_xtrig_reset_diag_data())
        bits.append(self.sample_cycles_data())
        bits.append(self.test_burst_length_data(0))
        bits.append(self.test_burst_length_data(1))
        bits.append(self.adc_burst_length_data())
        for chunk in range(4):
            bits.append(self.channel_mask_data(chunk))
        for chunk in range(4):
            bits.append(self.external_trigger_mask_data(chunk))
        bits.append(self.reset_cycles_data(0))
        bits.append(self.reset_cycles_data(1))
        bits.append(self.reset_cycles_data(2))
        return bits

    def _to8bits(self, number):
        return Bits('uint:8=' + str(number))

    def trim_threshold_data(self, channel):
        return self._to8bits(self.pixel_trim_thresholds[channel])

    def global_threshold_data(self):
        return self._to8bits(self.global_threshold)

    def csa_gain_and_bypasses_data(self):
        return Bits('0b0000') + [self.internal_bypass, 0,
                self.csa_bypass, self.csa_gain]

    def csa_bypass_select_data(self, chunk):
        if chunk == 0:
            return Bits(self.csa_bypass_select[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.csa_bypass_select[high_bit:low_bit:-1])

    def csa_monitor_select_data(self, chunk):
        if chunk == 0:
            return Bits(self.csa_monitor_select[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.csa_monitor_select[high_bit:low_bit:-1])

    def csa_testpulse_enable_data(self, chunk):
        if chunk == 0:
            return Bits(self.csa_testpulse_enable[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.csa_testpulse_enable[high_bit:low_bit:-1])

    def csa_testpulse_dac_amplitude_data(self):
        return self._to8bits(self.csa_testpulse_dac_amplitude)

    def test_mode_xtrig_reset_diag_data(self):
        toReturn = BitArray([0, 0, 0, self.fifo_diagnostic,
            self.periodic_reset,
            self.cross_trigger_mode])
        toReturn.append('uint:2=' + str(self.test_mode))
        return toReturn

    def sample_cycles_data(self):
        return self._to8bits(self.sample_cycles)

    def test_burst_length_data(self, chunk):
        bits = Bits('uint:16=' + str(self.test_burst_length))
        if chunk == 0:
            return bits[8:]
        elif chunk == 1:
            return bits[:8]

    def adc_burst_length_data(self):
        return self._to8bits(self.adc_burst_length)

    def channel_mask_data(self, chunk):
        if chunk == 0:
            return Bits(self.channel_mask[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.channel_mask[high_bit:low_bit:-1])

    def external_trigger_mask_data(self, chunk):
        if chunk == 0:
            return Bits(self.external_trigger_mask[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.external_trigger_mask[high_bit:low_bit:-1])

    def reset_cycles_data(self, chunk):
        bits = Bits('uint:24=' + str(self.reset_cycles))
        if chunk == 0:
            return bits[16:]
        elif chunk == 1:
            return bits[8:16]
        elif chunk == 2:
            return bits[:8]

    def to_dict(self):
        d = {}
        for register_name in self.register_names:
            d[register_name] = getattr(self, register_name)
        return d

    def from_dict(self, d):
        for register_name in self.register_names:
            if register_name in d:
                setattr(self, register_name, d[register_name])

    def write(self, filename, force=False, append=False):
        if os.path.isfile(filename):
            if not force:
                raise IOError(errno.EEXIST,
                              'File %s exists. Use force=True to overwrite'
                              % filename)

        with open(filename, 'w+') as outfile:
            outfile.write(str(self))
        return 0

    def load(self, filename):
        data = configs.load(filename)
        self.from_dict(data)

class Controller(object):
    '''
    Controls a collection of LArPix Chip objects.

    '''
    start_byte = b'\x73'
    stop_byte = b'\x71'
    def __init__(self, port='/dev/ttyUSB1'):
        self.chips = []
        self.port = port
        self.baudrate = 1000000
        self.timeout = 1
        self.max_write = 8192
        self.read_counter = 0
        self.last_read_time = 0
        self._serial = serial.Serial

    def init_chips(self, nchips = 256, iochain = 0):
        self.chips = [Chip(i, iochain) for i in range(256)]

    def get_chip(self, chip_id, io_chain):
        for chip in self.chips:
            if chip.chip_id == chip_id and chip.io_chain == io_chain:
                return chip
        raise ValueError('Could not find chip (%d, %d)' % (chip_id,
            io_chain))

    def serial_flush(self):
        with self._serial(self.port, baudrate=self.baudrate,
                timeout=self.timeout) as serial:
            serial.reset_output_buffer()
            serial.reset_input_buffer()

    def serial_read(self, timelimit):
        data_in = b''
        start = time.time()
        self.last_read_time = start
        self.read_counter += 1
        try:
            with self._serial(self.port, baudrate=self.baudrate,
                    timeout=self.timeout) as serial_in:
                while time.time() - start < timelimit:
                    stream = serial_in.read(self.max_write)
                    if len(stream) > 0:
                        data_in += stream
        except Exception as e:
            if getattr(self, '_read_tries_left', None) is None:
                self._read_tries_left = 3
                self.serial_read(timelimit)
            elif self._read_tries_left > 0:
                self._read_tries_left -= 1
                self.serial_read(timelimit)
            else:
                del self._read_tries_left
                raise
        return data_in

    def serial_write(self, bytestreams):
        with self._serial(self.port, baudrate=self.baudrate,
                timeout=self.timeout) as output:
            for bytestream in bytestreams:
                output.write(bytestream)

    def serial_write_read(self, bytestreams, timelimit):
        data_in = b''
        start = time.time()
        self.last_read_time = start
        self.read_counter += 1
        with self._serial(self.port, baudrate=self.baudrate) as serial_port:
            # First do a fast write-read loop until everything is
            # written out, then just read
            serial_port.timeout = 0  # Return whatever's already waiting
            for bytestream in bytestreams:
                serial_port.write(bytestream)
                stream = serial_port.read(self.max_write)
                if len(stream) > 0:
                    data_in += stream
            serial_port.timeout = self.timeout
            while time.time() - start < timelimit:
                stream = serial_port.read(self.max_write)
                if len(stream) > 0:
                    data_in += stream
        return data_in

    def write_configuration(self, chip, registers=None, write_read=0):
        if registers is None:
            registers = list(range(Configuration.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        bytestreams = self.get_configuration_bytestreams(chip,
                Packet.CONFIG_WRITE_PACKET, registers)
        if write_read == 0:
            self.serial_write(bytestreams)
            return b''
        else:
            return self.serial_write_read(bytestreams,
                    timelimit=write_read)

    def read_configuration(self, chip, registers=None):
        if registers is None:
            registers = list(range(Configuration.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        bytestreams = self.get_configuration_bytestreams(chip,
                Packet.CONFIG_READ_PACKET, registers)
        data = self.serial_write_read(bytestreams, 1)
        unprocessed = self.parse_input(data)
        return unprocessed

    def get_configuration_bytestreams(self, chip, packet_type, registers):
        # The configuration must be sent one register at a time
        configuration_packets = \
            chip.get_configuration_packets(packet_type);
        for i in range(len(configuration_packets)-1, -1, -1):
            if i not in registers:
                del configuration_packets[i]
        formatted_packets = [self.format_UART(chip, p) for p in
                configuration_packets]
        bytestreams = self.format_bytestream(formatted_packets)
        return bytestreams

    def run(self, timelimit):
        data = self.serial_read(timelimit)
        self.parse_input(data)

    def run_testpulse(self, list_of_channels):
        return

    def run_fifo_test(self):
        return

    def run_analog_monitor_test(self):
        return

    def format_UART(self, chip, packet):
        packet_bytes = packet.bytes()
        daisy_chain_byte = (4 + Bits('uint:4=' + str(chip.io_chain))).bytes
        formatted_packet = (Controller.start_byte + packet_bytes +
                daisy_chain_byte + Controller.stop_byte)
        return formatted_packet

    def parse_input(self, bytestream):
        packet_size = 10
        start_byte = Controller.start_byte[0]
        stop_byte = Controller.stop_byte[0]
        metadata_byte_index = 8
        data_bytes = slice(1,8)
        # parse the bytestream into Packets + metadata
        byte_packets = []
        current_stream = bytestream
        current_byte = 0
        while len(current_stream) >= packet_size:
            if (current_stream[0] == start_byte and
                    current_stream[packet_size-1] == stop_byte):
                metadata = current_stream[metadata_byte_index]
                # This is necessary because of differences between
                # Python 2 and Python 3
                if isinstance(metadata, int):  # Python 3
                    code = 'uint:8='
                elif isinstance(metadata, str):  # Python 2
                    code = 'bytes:1='
                byte_packets.append((Bits(code + str(metadata)),
                    Packet(current_stream[data_bytes])))
                byte_packets[-1][1].cpu_timestamp = self.last_read_time
                byte_packets[-1][1].read_id = self.read_counter
                byte_packets[-1][1].bytestream_id = current_byte
                        # store postion in bytestream of packet
                current_stream = current_stream[packet_size:]
            else:
                # Throw out everything between here and the next start byte.
                # Note: start searching after byte 0 in case it's
                # already a start byte
                next_start_index = current_stream[1:].find(start_byte)
                current_byte += next_start_index
                current_stream = current_stream[1:][next_start_index:]

        for chip in self.chips:
            read_data = {}
            read_data['cpu_timestamp'] = self.last_read_time
            read_data['read_id'] = self.read_counter
            read_data['config'] = chip.config.get_nondefault_registers()
            read_data['log_message'] = ''
            read_data['packets'] = []
            chip.reads.append(read_data)
        # assign each packet to the corresponding Chip
        for byte_packet in byte_packets:
            io_chain = byte_packet[0][4:].uint
            packet = byte_packet[1]
            chip_id = packet.chipid
            self.get_chip(chip_id, io_chain).reads[-1]['packets'].append(packet)
        return current_stream  # (the remainder that wasn't read in)

    def format_bytestream(self, formatted_packets):
        bytestreams = []
        current_bytestream = bytes()
        for packet in formatted_packets:
            if len(current_bytestream) + len(packet) < self.max_write:
                current_bytestream += packet
            else:
                bytestreams.append(current_bytestream)
                current_bytestream = bytes()
                current_bytestream += packet
        bytestreams.append(current_bytestream)
        return bytestreams

    def save_output(self, filename):
        '''Save the data read by each chip to the specified file.'''
        data = {}
        data['chips'] = list(map(lambda x:x.export_reads(), self.chips))
        with open(filename, 'w') as outfile:
            json.dump(data, outfile, indent=4,
                    separators=(',',':'), sort_keys=True)



class Packet(object):
    '''
    A single 54-bit LArPix UART data packet.

    '''
    size = 54
    num_bytes = 7
    # These ranges are reversed from the bit addresses given in the
    # LArPix datasheet because BitArray indexing is big-endian but we
    # transmit data little-endian-ly. E.g.:
    # >>> x = BitArray('0b00')
    # >>> x[0:] = bin(2)  # ('0b10')
    # >>> x[0]  # returns True (1)
    # Another way to think of it is BitArray indexing reads the
    # bitstream from 0:N but all the LArPix datasheet indexing goes from
    # N:0.
    packet_type_bits = slice(52, 54)
    chipid_bits = slice(44, 52)
    parity_bit = 0
    parity_calc_bits = slice(1, 54)
    channel_id_bits = slice(37, 44)
    timestamp_bits = slice(13, 37)
    dataword_bits = slice(3, 13)
    fifo_half_bit = 2
    fifo_full_bit = 1
    register_address_bits = slice(36, 44)
    register_data_bits = slice(28, 36)
    config_unused_bits = slice(1, 28)
    test_counter_bits_11_0 = slice(1, 13)
    test_counter_bits_15_12 = slice(40, 44)

    DATA_PACKET = Bits('0b00')
    TEST_PACKET = Bits('0b01')
    CONFIG_WRITE_PACKET = Bits('0b10')
    CONFIG_READ_PACKET = Bits('0b11')

    def __init__(self, bytestream=None):
        self._bit_padding = Bits('0b00')
        self._cpu_timestamp = time.time()
        self._read_id = 0
        self._bytestream_id = 0
        if bytestream is None:
            self.bits = BitArray(Packet.size)
            return
        elif len(bytestream) == Packet.num_bytes:
            # Parse the bytestream. Remember that bytestream[0] goes at
            # the 'end' of the BitArray
            reversed_bytestream = bytestream[::-1]
            bits_with_padding = BitArray(bytes=reversed_bytestream)
            self.bits = bits_with_padding[len(self._bit_padding):]
        else:
            raise ValueError('Invalid number of bytes: %s' %
                    len(bytestream))

    def __eq__(self, other):
        return self.bits == other.bits

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        string = '[ '
        ptype = self.packet_type
        if ptype == Packet.TEST_PACKET:
            string += 'Test | '
            string += 'Counter: %d | ' % self.test_counter
        elif ptype == Packet.DATA_PACKET:
            string += 'Data | '
            string += 'Channel: %d | ' % self.channel_id
            string += 'Timestamp: %d | ' % self.timestamp
            string += 'ADC data: %d | ' % self.dataword
            string += 'FIFO Half: %s | ' % bool(self.fifo_half_flag)
            string += 'FIFO Full: %s | ' % bool(self.fifo_full_flag)
        elif (ptype == Packet.CONFIG_READ_PACKET or ptype ==
                Packet.CONFIG_WRITE_PACKET):
            if ptype == Packet.CONFIG_READ_PACKET:
                string += 'Config read | '
            else:
                string += 'Config write | '
            string += 'Register: %d | ' % self.register_address
            string += 'Value: % d | ' % self.register_data
        string += 'CPU Time: %d | ' % self.cpu_timestamp
        string += 'Read id: %d | ' % self.read_id
        string += 'Bytestream id: %d | ' % self.bytestream_id
        first_splitter = string.find('|')
        string = (string[:first_splitter] + '| Chip: %d ' % self.chipid +
                string[first_splitter:])
        string += ('Parity: %d (valid: %s) ]' %
                (self.parity_bit_value, self.has_valid_parity()))
        return string

    def __repr__(self):
        return 'Packet(' + str(self.bytes()) + ')'

    def bytes(self):
        # Here's the only other place we have to deal with the
        # endianness issue by reversing the order
        padded_output = self._bit_padding + self.bits
        bytes_output = padded_output.bytes
        return bytes_output[::-1]

    def export(self):
        '''Return a dict representation of this Packet.'''
        type_map = {
                Bits(self.TEST_PACKET): 'test',
                Bits(self.DATA_PACKET): 'data',
                Bits(self.CONFIG_WRITE_PACKET): 'config write',
                Bits(self.CONFIG_READ_PACKET): 'config read'
                }
        d = {}
        d['bits'] = self.bits.bin
        d['type'] = type_map[Bits(self.packet_type)]
        d['chipid'] = self.chipid
        d['cpu_timestamp'] = self.cpu_timestamp
        d['read_id'] = self.read_id
        d['bytestream_id'] = self.bytestream_id
        d['parity'] = self.parity_bit_value
        d['valid_parity'] = self.has_valid_parity()
        ptype = self.packet_type
        if ptype == Packet.TEST_PACKET:
            d['counter'] = self.test_counter
        elif ptype == Packet.DATA_PACKET:
            d['channel'] = self.channel_id
            d['timestamp'] = self.timestamp
            d['adc_counts'] = self.dataword
            d['fifo_half'] = bool(self.fifo_half_flag)
            d['fifo_full'] = bool(self.fifo_full_flag)
        elif (ptype == Packet.CONFIG_READ_PACKET or ptype ==
                Packet.CONFIG_WRITE_PACKET):
            d['register'] = self.register_address
            d['value'] = self.register_data
        return d

    @property
    def packet_type(self):
        return self.bits[Packet.packet_type_bits]

    @packet_type.setter
    def packet_type(self, value):
        self.bits[Packet.packet_type_bits] = value

    @property
    def chipid(self):
        return self.bits[Packet.chipid_bits].uint

    @chipid.setter
    def chipid(self, value):
        self.bits[Packet.chipid_bits] = value

    @property
    def cpu_timestamp(self):
        return self._cpu_timestamp

    @cpu_timestamp.setter
    def cpu_timestamp(self, value):
        self._cpu_timestamp = value

    @property
    def read_id(self):
        return self._read_id

    @read_id.setter
    def read_id(self, value):
        self._read_id = value

    @property
    def bytestream_id(self):
        return self._bytestream_id

    @bytestream_id.setter
    def bytestream_id(self, value):
        self._bytestream_id = value

    @property
    def parity_bit_value(self):
        return int(self.bits[Packet.parity_bit])

    @parity_bit_value.setter
    def parity_bit_value(self, value):
        self.bits[Packet.parity_bit] = value

    def compute_parity(self):
        return 1 - (self.bits[Packet.parity_calc_bits].count(True) % 2)

    def assign_parity(self):
        self.parity_bit_value = self.compute_parity()

    def has_valid_parity(self):
        return self.parity_bit_value == self.compute_parity()

    @property
    def channel_id(self):
        return self.bits[Packet.channel_id_bits].uint

    @channel_id.setter
    def channel_id(self, value):
        self.bits[Packet.channel_id_bits] = value

    @property
    def timestamp(self):
        return self.bits[Packet.timestamp_bits].uint

    @timestamp.setter
    def timestamp(self, value):
        self.bits[Packet.timestamp_bits] = value

    @property
    def dataword(self):
        return self.bits[Packet.dataword_bits].uint

    @dataword.setter
    def dataword(self, value):
        self.bits[Packet.dataword_bits] = value

    @property
    def fifo_half_flag(self):
        return int(self.bits[Packet.fifo_half_bit])

    @fifo_half_flag.setter
    def fifo_half_flag(self, value):
        self.bits[Packet.fifo_half_bit] = bool(value)

    @property
    def fifo_full_flag(self):
        return int(self.bits[Packet.fifo_full_bit])

    @fifo_full_flag.setter
    def fifo_full_flag(self, value):
        self.bits[Packet.fifo_full_bit] = bool(value)

    @property
    def register_address(self):
        return self.bits[Packet.register_address_bits].uint

    @register_address.setter
    def register_address(self, value):
        self.bits[Packet.register_address_bits] = value

    @property
    def register_data(self):
        return self.bits[Packet.register_data_bits].uint

    @register_data.setter
    def register_data(self, value):
        self.bits[Packet.register_data_bits] = value

    @property
    def test_counter(self):
        return (self.bits[Packet.test_counter_bits_15_12] +
                self.bits[Packet.test_counter_bits_11_0]).uint

    @test_counter.setter
    def test_counter(self, value):
        allbits = BitArray('uint:16=' + str(value))
        self.bits[Packet.test_counter_bits_15_12] = allbits[:4]
        self.bits[Packet.test_counter_bits_11_0] = allbits[4:]
