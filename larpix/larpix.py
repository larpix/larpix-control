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

    def __repr__(self):
        return 'Chip(%d, %d)' % (self.chip_id, self.io_chain)

    def get_configuration_packets(self, packet_type):
        conf = self.config
        packets = [Packet() for _ in range(Configuration.num_registers)]
        packet_register_data = conf.all_data()
        for i, (packet, data) in enumerate(zip(packets, packet_register_data)):
            packet.packet_type = packet_type
            packet.chipid = self.chip_id
            packet.register_address = i
            if packet_type == Packet.CONFIG_WRITE_PACKET:
                packet.register_data = data
            else:
                packet.register_data = 0
            packet.assign_parity()
        return packets

    def sync_configuration(self):
        '''
        Adjust self.config to match whatever config read packets are in
        self.reads.

        Later packets in the list will overwrite earlier packets.

        '''
        updates = {}
        for packet in self.reads:
            if packet.packet_type == Packet.CONFIG_READ_PACKET:
                updates[packet.register_address] = packet.register_data

        self.config.from_dict_registers(updates)

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
            packets = self.reads[self.new_reads_index:]
        else:
            packets = self.reads
        data['packets'] = list(map(lambda x:x.export(), packets))
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
    register_names = ['pixel_trim_thresholds',
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

    TEST_OFF = 0x0
    TEST_UART = 0x1
    TEST_FIFO = 0x2
    def __init__(self):
        # Actual setup
        self.load('default.json')

        # Annoying things we have to do because the configuration
        # register follows complex semantics:
        # The following dicts/lists specify how to translate a register
        # address into a sensible update to the Configuration object.
        # Simple registers are just the value stored in the register.
        self._simple_registers = {
                32: 'global_threshold',
                46: 'csa_testpulse_dac_amplitude',
                48: 'sample_cycles',
                51: 'adc_burst_length',
                }
        # These registers need the attribute extracted from the register
        # data.
        self._complex_modify_data = {
                33: [('csa_gain', lambda data:data % 2),
                     ('csa_bypass', lambda data:(data//2) % 2),
                     ('internal_bypass', lambda data:(data//8) % 2)],
                47: [('test_mode', lambda data:data % 4),
                     ('cross_trigger_mode', lambda data:(data//4) % 2),
                     ('periodic_reset', lambda data:(data//8) % 2),
                     ('fifo_diagnostic', lambda data:(data//16) % 2)]
                }
        # These registers combine the register data with the existing
        # attribute value to get the new attribute value.
        self._complex_modify_attr = {
                49: ('test_burst_length', lambda val,data:(val//256)*256+data),
                50: ('test_burst_length', lambda val,data:(val%256)+data*256),
                60: ('reset_cycles', lambda val,data:(val//256)*256+data),
                61: ('reset_cycles',
                    lambda val,data:(val//0x10000)*0x10000+data*256+val%256),
                62: ('reset_cycles', lambda val,data:(val%0x10000)+data*0x10000)
                }
        # These registers store 32 bits over 4 registers each, and those
        # 32 bits correspond to entries in a 32-entry list.
        complex_array_spec = [
                (range(34, 38), 'csa_bypass_select'),
                (range(38, 42), 'csa_monitor_select'),
                (range(42, 46), 'csa_testpulse_enable'),
                (range(52, 56), 'channel_mask'),
                (range(56, 60), 'external_trigger_mask')]
        self._complex_array = {}
        for addresses, label in complex_array_spec:
            for i, address in enumerate(addresses):
                self._complex_array[address] = (label, i)
        # These registers each correspond to an entry in an array
        self._trim_registers = list(range(32))

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

    def from_dict_registers(self, d):
        '''
        Load in the configuration specified by a dict of (register,
        value) pairs.

        '''
        def bits_to_array(data):
            bits = Bits('uint:8=%d' % data)
            return [int(bit) for bit in bits][::-1]

        for address, value in d.items():
            if address in self._simple_registers:
                setattr(self, self._simple_registers[address], value)
            elif address in self._complex_modify_data:
                attributes = self._complex_modify_data[address]
                for name, extract in attributes:
                    setattr(self, name, extract(value))
            elif address in self._complex_modify_attr:
                name, combine = self._complex_modify_attr[address]
                current_value = getattr(self, name)
                setattr(self, name, combine(current_value, value))
            elif address in self._complex_array:
                name, index = self._complex_array[address]
                affected = slice(index*8, (index+1)*8)
                attr_list = getattr(self, name)
                attr_list[affected] = bits_to_array(value)
            elif address in self._trim_registers:
                self.pixel_trim_thresholds[address] = value
        return  #phew

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
        self.reads = []
        self.nreads = 0
        self.port = port
        self.baudrate = 1000000
        self.timeout = 1
        self.max_write = 8192
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
        else:
            miso_bytestream = self.serial_write_read(bytestreams,
                    timelimit=write_read)
            packets = self.parse_input(miso_bytestream)
            self.store_packets(packets, miso_bytestream, 'configuration write')

    def read_configuration(self, chip, registers=None, timeout=1):
        if registers is None:
            registers = list(range(Configuration.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        bytestreams = self.get_configuration_bytestreams(chip,
                Packet.CONFIG_READ_PACKET, registers)
        data = self.serial_write_read(bytestreams, timeout)
        packets = self.parse_input(data)
        self.store_packets(packets, data, 'configuration read')

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

    def run(self, timelimit, message):
        data = self.serial_read(timelimit)
        packets = self.parse_input(data)
        self.store_packets(packets, data, message)

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
                current_stream = current_stream[packet_size:]
            else:
                # Throw out everything between here and the next start byte.
                # Note: start searching after byte 0 in case it's
                # already a start byte
                next_start_index = current_stream[1:].find(start_byte)
                current_stream = current_stream[1:][next_start_index:]
        return [x[1] for x in byte_packets]

    def store_packets(self, packets, data, message):
        '''
        Store the packets in ``self`` and in ``self.chips``

        '''
        new_packets = PacketCollection(packets, data, message)
        new_packets.read_id = self.nreads
        self.nreads += 1
        self.reads.append(new_packets)
        self.sort_packets(new_packets)


    def sort_packets(self, collection):
        '''
        Sort the packets in ``collection`` into each chip in
        ``self.chips``.

        '''
        by_chipid = collection.by_chipid()
        for chip in self.chips:
            if chip.chip_id in by_chipid:
                message = collection.message + ' | chip %d' % chip.chip_id
                chip_packets = PacketCollection(by_chipid[chip.chip_id],
                        message=message)
                chip.reads.append(chip_packets)


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
        ostensible_value = self.bits[Packet.dataword_bits].uint
        # TODO fix in LArPix v2
        return ostensible_value - (ostensible_value % 2)

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

class PacketCollection(object):
    '''
    Represents a group of packets that were sent to or received from
    LArPix.

    Index into the PacketCollection as if it were a list:

        >>> collection[0]
        Packet(b'\x07\x00\x00\x00\x00\x00\x00')
        >>> first_ten = collection[:10]
        >>> len(first_ten)
        10
        >>> type(first_ten)
        larpix.larpix.PacketCollection
        >>> first_ten.message
        'my packets | subset slice(None, 10, None)'

    To view the bits representation, add 'bits' to the index:

        >>> collection[0, 'bits']
        '00000000 00000000 00000000 00000000 00000000 00000000 000111'
        >>> bits_format_first_10 = collection[:10, 'bits']
        >>> type(bits_format_first_10[0])
        str


    '''
    def __init__(self, packets, bytestream=None, message='', read_id=None):
        self.packets = packets
        self.bytestream = bytestream
        self.message = message
        self.read_id = read_id
        self.parent = None

    def __eq__(self, other):
        '''
        Return True if the packets, message and bytestream compare equal.

        '''
        return (self.packets == other.packets and
                self.message == other.message and
                self.bytestream == other.bytestream)

    def __repr__(self):
        return '<%s with %d packets, read_id %d, "%s">' % (self.__class__.__name__,
                len(self.packets), self.read_id, self.message)

    def __str__(self):
        if len(self.packets) < 20:
            return '\n'.join(str(packet) for packet in self.packets)
        else:
            beginning = '\n'.join(str(packet) for packet in self.packets[:10])
            middle = '\n'.join(['   .', '   . omitted %d packets' %
                (len(self.packets)-20), '   .'])
            end = '\n'.join(str(packet) for packet in self.packets[-10:])
            return '\n'.join([beginning, middle, end])

    def __len__(self):
        return len(self.packets)

    def __getitem__(self, key):
        '''
        Get the specified item(s).

        If key is an int, return the packet object at that index in
        self.packets.

        If key is a slice, return a PacketCollection with the specified
        packets, and with a message inherited from self.message.

        If key is (slice or int, 'str'), use the behavior as if setting
        key = key[0].

        If key is (int, 'bits'), return a string representation of the
        bits of the specified packet, as determined by
        self._bits_getitem.

        If key is (slice, 'bits'), return a list of string
        representations of the packets specified by the slice.

        '''
        if isinstance(key, slice):
            items = PacketCollection([p for p in self.packets[key]])
            items.message = '%s | subset %s' % (self.message, key)
            items.parent = self
            return items
        elif isinstance(key, tuple):
            if key[1] == 'bits':
                return self._bits_getitem(key[0])
            elif key[1] == 'str':
                return self[key[0]]
        else:
            return self.packets[key]

    def _bits_getitem(self, key):
        '''
        Replace each packet with a string of the packet bits grouped 8
        bits at a time.

        '''
        if isinstance(key, slice):
            return [' '.join(p.bits.bin[i:i+8] for i in
                range(0, Packet.size, 8)) for p in self.packets[key]]
        else:
            return ' '.join(self.packets[key].bits.bin[i:i+8] for i in
                    range(0, Packet.size, 8))

    def with_chipid(self, chipid):
        '''
        Return packets with the specified chip ID.

        '''
        return [packet for packet in self.packets if packet.chipid == chipid]

    def by_chipid(self):
        '''
        Return a dict of { chipid: [packet] }.

        '''
        to_return = {}
        for packet in self.packets:
            # append packet to list if list exists, else append to empty
            # list as a default
            to_return.setdefault(packet.chipid, []).append(packet)
        return to_return
