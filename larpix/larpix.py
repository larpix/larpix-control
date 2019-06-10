'''
A module to control the LArPix chip.

'''
from __future__ import absolute_import
from __future__ import print_function
import time
import json
import os
import errno
import math
import warnings

from bitarray import bitarray

from . import bitarrayhelper as bah
from . import configs

class Chip(object):
    '''
    Represents one LArPix chip and helps with configuration and packet
    generation.

    '''
    num_channels = 32
    def __init__(self, chip_id, chip_key):
        '''
        Create a new Chip object with the given ``chip_id``. The specification
        of the ``chip_key`` is given by each ``io`` class.

        '''
        self.chip_id = chip_id
        self.chip_key = chip_key
        self.data_to_send = []
        self.config = Configuration()
        self.reads = []
        self.new_reads_index = 0

    def __str__(self):
        return 'Chip (id: {}, key: {})'.format(self.chip_id, self.chip_key)

    def __repr__(self):
        return 'Chip(chip_id={}, chip_key={})'.format(self.chip_id, self.chip_key)

    def get_configuration_packets(self, packet_type, registers=None):
        '''
        Return a list of Packet objects to read or write (depending on
        ``packet_type``) the specified configuration registers (or all
        registers by default).

        '''
        if registers is None:
            registers = range(Configuration.num_registers)
        conf = self.config
        packets = []
        packet_register_data = conf.all_data()
        for i, data in enumerate(packet_register_data):
            if i not in registers:
                continue
            packet = Packet()
            packet.packet_type = packet_type
            packet.chipid = self.chip_id
            packet.chip_key = self.chip_key
            packet.register_address = i
            if packet_type == Packet.CONFIG_WRITE_PACKET:
                packet.register_data = data
            else:
                packet.register_data = 0
            packet.assign_parity()
            packets.append(packet)
        return packets

    def sync_configuration(self, index=-1):
        '''
        Adjust self.config to match whatever config read packets are in
        self.reads[index].

        Defaults to the most recently read PacketCollection. Later
        packets in the list will overwrite earlier packets. The
        ``index`` parameter could be a slice.

        '''
        updates = {}
        if isinstance(index, slice):
            for collection in self.reads[index]:
                for packet in collection:
                    if packet.packet_type == Packet.CONFIG_READ_PACKET:
                        updates[packet.register_address] = packet.register_data
        else:
            for packet in self.reads[index]:
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
        data['chip_key'] = self.chip_key
        data['chip_id'] = self.chip_id
        if only_new_reads:
            packets = self.reads[self.new_reads_index:]
        else:
            packets = self.reads
        data['packets'] = list(map(lambda x:x.export(), packets))
        self.new_reads_index = len(self.reads)
        return data

class _Smart_List(list):
    '''
    A list type which checks its elements to be within given bounds.
    Used for Configuration attributes where there's a distinct value for
    each LArPix channel.

    '''

    def __init__(self, values, low, high):
        if not (type(values) == list or type(values) == _Smart_List):
            raise ValueError("_Smart_List is not list")
        if any([value > high or value < low for value in values]):
            raise ValueError("value out of bounds")
        list.__init__(self, values)
        self.low = low
        self.high = high

    def __setitem__(self, key, value):
        if isinstance(key, int):
            if value > self.high or value < self.low:
                raise ValueError("value out of bounds")
            list.__setitem__(self, key, value)
        else:
            for num in value:
                if num > self.high or num < self.low:
                    raise ValueError("value out of bounds")
            list.__setitem__(self, key, value)

    def __setslice__(self, i, j, value):
        '''
        Only used in Python 2, where __setslice__ is deprecated but
        contaminates the namespace of this subclass.

        '''
        self.__setitem__(slice(i, j, None), value)


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
    '''
    This attribute lists the names of all available configuration
    registers. Each register name is available as its own attribute for
    inspecting and setting the value of the corresponding register.

    Certain configuration values are set channel-by-channel. These are
    represented by a list of values. For example:

        >>> conf.pixel_trim_thresholds[2:5]
        [16, 16, 16]
        >>> conf.channel_mask[20] = 1
        >>> conf.external_trigger_mask = [0] * 32

    Additionally, other configuration values take up more than or less
    than one complete register. These are still set by referencing the
    appropriate name. For example, ``cross_trigger_mode`` shares a
    register with a few other values, and adjusting the value of the
    ``cross_trigger_mode`` attribute will leave the other values
    unchanged.

    '''

    TEST_OFF = 0x0
    TEST_UART = 0x1
    TEST_FIFO = 0x2
    def __init__(self):
        # Actual setup
        self.load('chip/default.json')

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
        self._complex_array_spec = [
                (range(34, 38), 'csa_bypass_select'),
                (range(38, 42), 'csa_monitor_select'),
                (range(42, 46), 'csa_testpulse_enable'),
                (range(52, 56), 'channel_mask'),
                (range(56, 60), 'external_trigger_mask')]
        self._complex_array = {}
        for addresses, label in self._complex_array_spec:
            for i, address in enumerate(addresses):
                self._complex_array[address] = (label, i)
        # These registers each correspond to an entry in an array
        self._trim_registers = list(range(32))

    def __setattr__(self, name, value):
        '''
        Default setattr behavior occurs if name is in ``register_names``, is "private"
        or is a known attribute
        Otherwise raises an attribute error

        '''
        if not (name in self.register_names or name[0] == '_' or hasattr(self, name)):
            raise AttributeError('%s is not a known register' % name)
        return super(Configuration, self).__setattr__(name, value)

    def __eq__(self, other):
        '''
        Returns true if all fields match
        '''
        return all([getattr(self, register_name) == getattr(other, register_name)
                    for register_name in self.register_names])

    def __str__(self):
        '''
        Converts configuration to a nicely formatted json string

        '''
        d = self.to_dict()
        l = ['\"{}\": {}'.format(key,value) for key,value in d.items()]
        return '{\n    ' + ',\n    '.join(l) + '\n}'

    def compare(self, config):
        '''
        Returns a dict containing pairs of each differently valued register
        Pair order is (self, other)
        '''
        d = {}
        for register_name in self.register_names:
            if getattr(self, register_name) != getattr(config, register_name):
                d[register_name] = (getattr(self, register_name), getattr(config,
                                                                          register_name))
        # Attempt to simplify some of the long values (array values)
        for (name, (self_value, config_value)) in d.items():
            if (name in (label for _, label in self._complex_array_spec)
                    or name == 'pixel_trim_thresholds'):
                different_values = []
                for ch, (val, config_val) in enumerate(zip(self_value, config_value)):
                    if val != config_val:
                        different_values.append(({'channel': ch, 'value': val},
                                                 {'channel': ch, 'value': config_val}))
                if len(different_values) < 5:
                    d[name] = different_values
                else:
                    pass
        return d

    def get_nondefault_registers(self):
        '''
        Return a dict of all registers that are not set to the default
        configuration (i.e. of the ASIC on power-up). The keys are the
        register name where there's a difference, and the values are
        tuples of (current, default) configuration values.

        '''
        return self.compare(Configuration())

    @property
    def pixel_trim_thresholds(self):
        return self._pixel_trim_thresholds

    @pixel_trim_thresholds.setter
    def pixel_trim_thresholds(self, values):
        low = 0
        high = 31
        if not (type(values) == list or type(values) == _Smart_List):
            raise ValueError("pixel_trim_threshold is not list")
        if not len(values) == Chip.num_channels:
            raise ValueError("pixel_trim_threshold length is not %d" % Chip.num_channels)
        if not all(type(value) == int for value in values):
            raise ValueError("pixel_trim_threshold is not int")
        if any(value > high or value < low for value in values):
            raise ValueError("pixel_trim_threshold out of bounds")

        self._pixel_trim_thresholds = _Smart_List(values, low, high)

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
        low = 0
        high = 1
        if not (type(values) == list or type(values) == _Smart_List):
            raise ValueError("csa_bypass_select is not list")
        if not len(values) == Chip.num_channels:
            raise ValueError("csa_bypass_select length is not %d" % Chip.num_channels)
        if not all(type(value) == int for value in values):
            raise ValueError("csa_bypass_select is not int")
        if any(value > high or value < low for value in values):
            raise ValueError("csa_bypass_select out of bounds")

        self._csa_bypass_select = _Smart_List(values, low, high)

    @property
    def csa_monitor_select(self):
        return self._csa_monitor_select

    @csa_monitor_select.setter
    def csa_monitor_select(self, values):
        low = 0
        high = 1
        if not (type(values) == list or type(values) == _Smart_List):
            raise ValueError("csa_monitor_select is not list")
        if not len(values) == Chip.num_channels:
            raise ValueError("csa_monitor_select length is not %d" % Chip.num_channels)
        if not all(type(value) == int for value in values):
            raise ValueError("csa_monitor_select is not int")
        if any(value > high or value < low for value in values):
            raise ValueError("csa_monitor_select out of bounds")

        self._csa_monitor_select = _Smart_List(values, low, high)

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
        '''
        Shortcut for changing the channel mask for the given
        channels to "enable" (i.e. 0).

        '''
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.channel_mask[channel] = 0

    def disable_channels(self, list_of_channels=None):
        '''
        Shortcut for changing the channel mask for the given channels
        to "disable" (i.e. 1).

        '''
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.channel_mask[channel] = 1

    def enable_external_trigger(self, list_of_channels=None):
        '''
        Shortcut for enabling the external trigger functionality for the
        given channels. (I.e. disabling the mask.)

        '''
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.external_trigger_mask[channel] = 0

    def disable_external_trigger(self, list_of_channels=None):
        '''
        Shortcut for disabling the external trigger functionality for
        the given channels. (I.e. enabling the mask.)

        '''
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.external_trigger_mask[channel] = 1

    def enable_testpulse(self, list_of_channels=None):
        '''
        Shortcut for enabling the test pulser for the given channels.

        '''
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.csa_testpulse_enable[channel] = 0

    def disable_testpulse(self, list_of_channels=None):
        '''
        Shortcut for disabling the test pulser for the given channels.

        '''
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.csa_testpulse_enable[channel] = 1

    def enable_analog_monitor(self, channel):
        '''
        Shortcut for enabling the analog monitor on the given channel.

        '''
        self.csa_monitor_select[channel] = 1

    def disable_analog_monitor(self):
        '''
        Shortcut for disabling the analog monitor (on all channels).

        '''
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

    def trim_threshold_data(self, channel):
        return bah.fromuint(self.pixel_trim_thresholds[channel], 8)

    def global_threshold_data(self):
        return bah.fromuint(self.global_threshold, 8)

    def csa_gain_and_bypasses_data(self):
        return bitarray('0000') + [self.internal_bypass, 0,
                self.csa_bypass, self.csa_gain]

    def csa_bypass_select_data(self, chunk):
        if chunk == 0:
            return bitarray(self.csa_bypass_select[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return bitarray(self.csa_bypass_select[high_bit:low_bit:-1])

    def csa_monitor_select_data(self, chunk):
        if chunk == 0:
            return bitarray(self.csa_monitor_select[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return bitarray(self.csa_monitor_select[high_bit:low_bit:-1])

    def csa_testpulse_enable_data(self, chunk):
        if chunk == 0:
            return bitarray(self.csa_testpulse_enable[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return bitarray(self.csa_testpulse_enable[high_bit:low_bit:-1])

    def csa_testpulse_dac_amplitude_data(self):
        return bah.fromuint(self.csa_testpulse_dac_amplitude, 8)

    def test_mode_xtrig_reset_diag_data(self):
        toReturn = bitarray([0, 0, 0, self.fifo_diagnostic,
            self.periodic_reset,
            self.cross_trigger_mode])
        toReturn.extend(bah.fromuint(self.test_mode, 2))
        return toReturn

    def sample_cycles_data(self):
        return bah.fromuint(self.sample_cycles, 8)

    def test_burst_length_data(self, chunk):
        bits = bah.fromuint(self.test_burst_length, 16)
        if chunk == 0:
            return bits[8:]
        elif chunk == 1:
            return bits[:8]

    def adc_burst_length_data(self):
        return bah.fromuint(self.adc_burst_length, 8)

    def channel_mask_data(self, chunk):
        if chunk == 0:
            return bitarray(self.channel_mask[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return bitarray(self.channel_mask[high_bit:low_bit:-1])

    def external_trigger_mask_data(self, chunk):
        if chunk == 0:
            return bitarray(self.external_trigger_mask[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return bitarray(self.external_trigger_mask[high_bit:low_bit:-1])

    def reset_cycles_data(self, chunk):
        bits = bah.fromuint(self.reset_cycles, 24)
        if chunk == 0:
            return bits[16:]
        elif chunk == 1:
            return bits[8:16]
        elif chunk == 2:
            return bits[:8]

    def to_dict(self):
        '''
        Export the configuration register names and values into a dict.

        '''
        d = {}
        for register_name in self.register_names:
            d[register_name] = getattr(self, register_name)
        return d

    def from_dict(self, d):
        '''
        Use a dict of ``{register_name, value}`` to update the current
        configuration. Not all registers must be in the dict - only
        those present will be updated.

        '''
        for register_name in self.register_names:
            if register_name in d:
                setattr(self, register_name, d[register_name])

    def from_dict_registers(self, d):
        '''
        Load in the configuration specified by a dict of (register,
        value) pairs.

        '''
        def bits_to_array(data):
            bits = bah.fromuint(data, 8)
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
        '''
        Save the configuration to a JSON file.

        '''
        if os.path.isfile(filename):
            if not force:
                raise IOError(errno.EEXIST,
                              'File %s exists. Use force=True to overwrite'
                              % filename)

        with open(filename, 'w+') as outfile:
            outfile.write(str(self))
        return 0

    def load(self, filename):
        '''
        Load a JSON file and use the contents to update the current
        configuration.

        '''
        data = configs.load(filename)
        self.from_dict(data)

class Controller(object):
    '''
    Controls a collection of LArPix Chip objects.

    Reading data:

    The specific interface for reading data is selected by specifying
    the ``io`` attribute. These objects all have
    similar behavior for reading in new data. On initialization, the
    object will discard any LArPix packets sent from ASICs. To begin
    saving incoming packets, call ``start_listening()``.
    Data will then build up in some form of internal register or queue.
    The queue can be emptied with a call to ``read()``,
    which empties the queue and returns a list of Packet objects that
    were in the queue. The ``io`` object will still be listening for
    new packets during and after this process. If the queue/register
    fills up, data may be discarded/lost. To stop saving incoming
    packets and retrieve any packets still in the queue, call
    ``stop_listening()``. While the Controller is listening,
    packets can be sent using the appropriate methods without
    interrupting the incoming data stream.

    Properties and attributes:

    - ``chips``: the ``Chip`` objects that the controller controls
    - ``all_chips``: all possible ``Chip`` objects (considering there are
      a finite number of chip IDs), initialized on object construction
    - ``reads``: list of all the PacketCollections that have been sent
      back to this controller. PacketCollections are created by
      ``run``, ``write_configuration``, ``read_configuration``,
      ``multi_write_configuration``, ``multi_read_configuration``, and
      ``store_packets``.
    - ``use_all_chips``: if ``True``, look up chip objects in
      ``self.all_chips``, else look up in ``self.chips`` (default:
      ``False``)

    '''
    def __init__(self):
        self.chips = {}
        self.all_chips = self._init_chips()
        self._use_all_chips = False
        self.reads = []
        self.nreads = 0
        self.io = None
        self.logger = None

    @property
    def use_all_chips(self):
        return self._use_all_chips

    @use_all_chips.setter
    def use_all_chips(self, value):
        warnings.warn('all_chips access is no longer supported, bad things may happen',
            FutureWarning)
        self._use_all_chips = value

    def _init_chips(self, nchips = 256, iochain = 0):
        '''
        Return all possible chips.

        '''
        return_dict = {}
        for i in range(nchips):
            key = '{}-{}'.format(iochain, i)
            return_dict[key] = Chip(i, chip_key=key)
        return return_dict

    def get_chip(self, chip_key):
        '''
        Retrieve the Chip object that this Controller associates with
        the given ``chip_key``.

        '''
        if self.use_all_chips:
            chip_dict = self.all_chips
        else:
            chip_dict = self.chips
        try:
            return chip_dict[chip_key]
        except KeyError:
            raise ValueError('Could not find chip using key <{}> '.format(chip_key))
        # raise ValueError('Could not find chip (%d, %d) (using all_chips'
        #         '? %s)' % (chip_id, io_chain, self.use_all_chips))

    def add_chip(self, chip_key, chip_id=0, safe=True):
        '''
        Add a specified chip to the Controller chips

        param: chip_key: chip key to specify unique chip
        param: chip_id: chip id to associate with chip
        param: safe: check if chip key is valid using current io

        '''
        valid_chip_key = True
        if safe:
            if self.io:
                valid_chip_key = self.io.is_valid_chip_key(chip_key)
            else:
                raise RuntimeError('No io object to validate chip key, run with safe=False to override')
        if valid_chip_key:
            self.chips[chip_key] = Chip(chip_id=chip_id, chip_key=chip_key)
            return self.chips[chip_key]
        warnings.warn('Invalid chip key, chip was not added! run with safe=False to override')
        return None

    def load(self, filename, safe=True):
        '''
        Loads the specified file that describes the chip ids and IO network

        :param filename: File path to configuration file
        :param safe: Flag to check chip keys against current io
        '''
        return self.load_controller(filename, safe=safe)

    def load_controller(self, filename, safe=True):
        '''
        Loads the specified file using the basic key, chip format
        The key, chip file format is:
        ``
        {
            "name": "<system name>",
            "chip_list": [[<chip key>, <chip id>],...]
        }
        ``
        The chip key is the Controller access key that gets communicated to/from
        the io object when sending and receiving packets.

        :param filename: File path to configuration file
        :param safe: Flag to check chip keys against current io

        '''
        system_info = configs.load(filename)
        chips = {}
        for chip_info in system_info['chip_list']:
            chip_id = chip_info[1]
            chip_key = chip_info[0]
            valid_key = True
            if safe:
                if self.io:
                    valid_chip_key = self.io.is_valid_chip_key(chip_key)
                else:
                    raise RuntimeError('No io object to validate chip key, run with'
                        ' safe=False to override')
            if valid_key:
                chips[chip_key] = Chip(chip_id, chip_key=chip_key)
            else:
                raise RuntimeError('Chip key {} is invalid for io {}, run with '
                    'safe=False to override'.format(chip_key, self.io))
        self.chips = chips
        return system_info['name']

    def load_daisy_chain(self, filename, safe=True):
        '''
        Loads the specified file in a basic daisy chain format
        Daisy chain file format is:
        ``
        {
                "name": "<board name>",
                "chip_list": [[<chip id>,<daisy chain>],...]
        }
        ``
        Position in daisy chain is specified by position in `chip_set` list
        returns board name of the loaded chipset configuration

        :param filename: File path to configuration file
        :param safe: Flag to check chip keys against current io
        '''
        board_info = configs.load(filename)
        chips = {}
        for chip_info in board_info['chip_list']:
            chip_id = chip_info[0]
            io_chain = chip_info[1]
            key = '{}-{}'.format(io_chain, chip_id)
            valid_chip_key = True
            if safe:
                if self.io:
                    valid_chip_key = self.io.is_valid_chip_key(chip_key)
                else:
                    raise RuntimeError('No io object to validate chip key, run '
                        'with safe=False to override')
            if valid_chip_key:
                chips[key] = Chip(chip_id, chip_key=key)
            else:
                raise RuntimeError('Chip key {} is invalid for io {}, run with '
                    'safe=False to override'.format(chip_key, self.io))

        self.chips = chips
        return board_info['name']

    def send(self, packets):
        '''
        Send the specified packets to the LArPix ASICs.

        '''
        timestamp = time.time()
        if self.io:
            self.io.send(packets)
        else:
            warnings.warn('no IO object exists, no packets sent', RuntimeWarning)
        if self.logger:
            self.logger.record(packets, data_type='SEND', timestamp=timestamp)

    def start_listening(self):
        '''
        Listen for packets to arrive.

        '''
        if self.io:
            self.io.start_listening()
        else:
            warnings.warn('no IO object exists, you have done nothing', RuntimeWarning)

    def stop_listening(self):
        '''
        Stop listening for new packets to arrive.

        '''
        if self.io:
            return self.io.stop_listening()
        else:
            warnings.warn('no IO object exists, you have done nothing', RuntimeWarning)

    def read(self):
        '''
        Read any packets that have arrived and return (packets,
        bytestream) where bytestream is the bytes that were received.

        The returned list will contain packets that arrived since the
        last call to ``read`` or ``start_listening``, whichever was most
        recent.

        '''
        timestamp = time.time()
        packets = []
        bytestream = b''
        if self.io:
            packets, bytestream = self.io.empty_queue()
        else:
            warnings.warn('no IO object exists, no packets will be received', RuntimeWarning)
        if self.logger:
            self.logger.record(packets, data_type='READ', timestamp=timestamp)
        return packets, bytestream

    def write_configuration(self, chip_key, registers=None, write_read=0,
            message=None):
        '''
        Send the configurations stored in chip.config to the LArPix
        ASIC.

        By default, sends all registers. If registers is an int, then
        only that register is sent. If registers is an iterable, then
        all of the registers in the iterable are sent.

        If write_read == 0 (default), the configurations will be sent
        and the current listening state will not be affected. If the
        controller is currently listening, then the listening state
        will not change and the value of write_read will be ignored. If
        write_read > 0 and the controller is not currently listening,
        then the controller will listen for ``write_read`` seconds
        beginning immediately before the packets are sent out, read the
        io queue, and save the packets into the ``reads`` data member.
        Note that the controller will only read the queue once, so if a
        lot of data is expected, you should handle the reads manually
        and set write_read to 0 (default).

        '''
        if registers is None:
            registers = list(range(Configuration.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        if message is None:
            message = 'configuration write'
        else:
            message = 'configuration write: ' + message
        chip = self.get_chip(chip_key)
        packets = chip.get_configuration_packets(
                Packet.CONFIG_WRITE_PACKET, registers)
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        mess_with_listening = write_read != 0 and not already_listening
        if mess_with_listening:
            self.start_listening()
            stop_time = time.time() + write_read
        self.send(packets)
        if mess_with_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def read_configuration(self, chip_key, registers=None, timeout=1,
            message=None):
        '''
        Send "configuration read" requests to the LArPix ASIC.

        By default, request all registers. If registers is an int, then
        only that register is reqeusted. If registers is an iterable,
        then all of the registers in the iterable are requested.

        If the controller is currently listening, then the requests
        will be sent and no change to the listening state will occur.
        (The value of ``timeout`` will be ignored.) If the controller
        is not currently listening, then the controller will listen
        for ``timeout`` seconds beginning immediately before the first
        packet is sent out, and will save any received packets in the
        ``reads`` data member.

        '''
        if registers is None:
            registers = list(range(Configuration.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        if message is None:
            message = 'configuration read'
        else:
            message = 'configuration read: ' + message
        chip = self.get_chip(chip_key)
        packets = chip.get_configuration_packets(
                Packet.CONFIG_READ_PACKET, registers)
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        if not already_listening:
            self.start_listening()
            stop_time = time.time() + timeout
        self.send(packets)
        if not already_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def multi_write_configuration(self, chip_reg_pairs, write_read=0,
            message=None):
        '''
        Send multiple write configuration commands at once.

        ``chip_reg_pairs`` should be a list/iterable whose elements are
        an valid arguments to ``Controller.write_configuration``,
        excluding the ``write_read`` argument. Just like in the single
        ``Controller.write_configuration``, setting ``write_read > 0`` will
        have the controller read data during and after it writes, for
        however many seconds are specified.

        Examples:

        These first 2 are equivalent and write the full configurations

        >>> controller.multi_write_configuration([chip_key1, chip_key2, ...])
        >>> controller.multi_write_configuration([(chip_key1, None), chip_key2, ...])

        These 2 write the specified registers for the specified chips
        in the specified order

        >>> controller.multi_write_configuration([(chip_key1, 1), (chip_key2, 2), ...])
        >>> controller.multi_write_configuration([(chip_key1, range(10)), chip_key2, ...])

        '''
        if message is None:
            message = 'multi configuration write'
        else:
            message = 'multi configuration write: ' + message
        packets = []
        for chip_reg_pair in chip_reg_pairs:
            if not isinstance(chip_reg_pair, tuple):
                chip_reg_pair = (chip_reg_pair, None)
            chip_key, registers = chip_reg_pair
            if registers is None:
                registers = list(range(Configuration.num_registers))
            elif isinstance(registers, int):
                registers = [registers]
            else:
                pass
            chip = self.get_chip(chip_key)
            one_chip_packets = chip.get_configuration_packets(
                    Packet.CONFIG_WRITE_PACKET, registers)
            packets.extend(one_chip_packets)
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        mess_with_listening = write_read != 0 and not already_listening
        if mess_with_listening:
            self.start_listening()
            stop_time = time.time() + write_read
        self.send(packets)
        if mess_with_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            #time.sleep(stop_time - time.time())
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def multi_read_configuration(self, chip_reg_pairs, timeout=1,
            message=None):
        '''
        Send multiple read configuration commands at once.

        ``chip_reg_pairs`` should be a list/iterable whose elements are
        chip keys (to read entire configuration) or (chip_key, registers)
        tuples to read only the specified register(s). Registers could
        be ``None`` (i.e. all), an ``int`` for that register only, or an
        iterable of ints.

        Examples:

        These first 2 are equivalent and read the full configurations

        >>> controller.multi_read_configuration([chip_key1, chip_key2, ...])
        >>> controller.multi_read_configuration([(chip_key1, None), chip_key2, ...])

        These 2 read the specified registers for the specified chips
        in the specified order

        >>> controller.multi_read_configuration([(chip_key1, 1), (chip_key2, 2), ...])
        >>> controller.multi_read_configuration([(chip_key1, range(10)), chip_key2, ...])

        '''
        if message is None:
            message = 'multi configuration read'
        else:
            message = 'multi configuration read: ' + message
        packets = []
        for chip_reg_pair in chip_reg_pairs:
            if not isinstance(chip_reg_pair, tuple):
                chip_reg_pair = (chip_reg_pair, None)
            chip_key, registers = chip_reg_pair
            if registers is None:
                registers = list(range(Configuration.num_registers))
            elif isinstance(registers, int):
                registers = [registers]
            else:
                pass
            chip = self.get_chip(chip_key)
            one_chip_packets = chip.get_configuration_packets(
                    Packet.CONFIG_READ_PACKET, registers)
            packets += one_chip_packets
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        if not already_listening:
            self.start_listening()
            stop_time = time.time() + timeout
        self.send(packets)
        if not already_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            #time.sleep(stop_time - time.time())
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def run(self, timelimit, message):
        '''
        Read data from the LArPix ASICs for the given ``timelimit`` and
        associate the received Packets with the given ``message``.

        '''
        sleeptime = 0.1
        self.start_listening()
        start_time = time.time()
        packets = []
        bytestreams = []
        while time.time() - start_time < timelimit:
            time.sleep(sleeptime)
            read_packets, read_bytestream = self.read()
            packets.extend(read_packets)
            bytestreams.append(read_bytestream)
        self.stop_listening()
        data = b''.join(bytestreams)
        self.store_packets(packets, data, message)

    def verify_configuration(self, chip_keys=None, timeout=0.1):
        '''
        Read chip configuration from specified chip(s) and return ``True`` if the
        read chip configuration matches the current configuration stored in chip instance.
        ``chip_keys`` can be a single chip key, a list of chip keys, or ``None``. If
        ``chip_keys`` is ``None`` all chips will be verified.

        Also returns a dict containing the values of registers that are different
        (read register, stored register)
        '''
        return_value = True
        different_fields = {}
        if chip_keys is None:
            return self.verify_configuration(chip_keys=list(self.chips.keys()))
        elif isinstance(chip_keys, list):
            for chip_key in chip_keys:
                match, chip_fields = self.verify_configuration(chip_keys=chip_key)
                if not match:
                    different_fields[chip_key] = chip_fields
                    return_value = False
        else:
            chip_key = chip_keys
            chip = self.get_chip(chip_key)
            self.read_configuration(chip_key, timeout=timeout)
            configuration_data = {}
            for packet in self.reads[-1]:
                if (packet.packet_type == Packet.CONFIG_READ_PACKET and
                    packet.chip_key == chip_key):
                    configuration_data[packet.register_address] = packet.register_data
            expected_data = {}
            for register_address, bits in enumerate(chip.config.all_data()):
                expected_data[register_address] = int(bits.to01(),2)
            if not configuration_data == expected_data:
                return_value = False
                for register_address in expected_data:
                    if register_address in configuration_data.keys():
                        if not configuration_data[register_address] == expected_data[register_address]:
                            different_fields[register_address] = (expected_data[register_address], configuration_data[register_address])
                    else:
                        different_fields[register_address] = (expected_data[register_address], None)
        return (return_value, different_fields)

    def read_channel_pedestal(self, chip_key, channel, run_time=0.1):
        '''
        Set channel threshold to 0 and report back on the recieved adcs from channel
        Returns mean, rms, and packet collection
        '''
        chip = self.get_chip(chip_key)
        # Store previous state
        prev_channel_mask = chip.config.channel_mask
        prev_global_threshold = chip.config.global_threshold
        prev_pixel_trim_thresholds = chip.config.pixel_trim_thresholds
        # Set new configuration
        self.disable(chip_key=chip_key)
        self.enable(chip_key=chip_key, channel_list=[channel])
        chip.config.global_threshold = 0
        chip.config.pixel_trim_thresholds = [31]*32
        chip.config.pixel_trim_thresholds[channel] = 0
        self.write_configuration(chip, Configuration.channel_mask_addresses +
                                 Configuration.pixel_trim_threshold_addresses +
                                 [Configuration.global_threshold_address])
        self.run(0.1,'clear buffer')
        # Collect data
        self.run(run_time,'read_channel_pedestal_c{}_ch{}'.format(chip_key, channel))
        self.disable(chip_key=chip_key)
        adcs = self.reads[-2].extract('adc_counts', chip_key=chip_key, channel=channel)
        mean = 0
        rms = 0
        if len(adcs) > 0:
            mean = float(sum(adcs)) / len(adcs)
            rms = math.sqrt(float(sum([adc**2 for adc in adcs]))/len(adcs) - mean**2)
        else:
            print('No packets received from chip {}, channel {}'.format(chip_key, channel))
        # Restore previous state
        chip.config.channel_mask = prev_channel_mask
        chip.config.global_threshold = prev_global_threshold
        chip.config.pixel_trim_thresholds = prev_pixel_trim_thresholds
        self.write_configuration(chip, Configuration.channel_mask_addresses +
                                 Configuration.pixel_trim_threshold_addresses +
                                 [Configuration.global_threshold_address])
        self.run(2,'clear buffer')
        return (adcs, mean, rms)

    def enable_analog_monitor(self, chip_key, channel):
        '''
        Enable the analog monitor on a single channel on the specified chip.
        Note: If monitoring a different chip, call disable_analog_monitor first to ensure
        that the monitor to that chip is disconnected.
        '''
        chip = self.get_chip(chip_key)
        chip.config.disable_analog_monitor()
        chip.config.enable_analog_monitor(channel)
        self.write_configuration(chip_key, Configuration.csa_monitor_select_addresses)
        return

    def disable_analog_monitor(self, chip_key=None, channel=None):
        '''
        Disable the analog monitor for a specified chip and channel, if none are specified
        disable the analog monitor for all chips in self.chips and all channels
        '''
        if chip_key is None:
            for chip in self.chips:
                self.disable_analog_monitor(chip_key=chip_key, channel=channel)
        elif channel is None:
            for channel in range(32):
                self.disable_analog_monitor(chip_key=chip_key, channel=channel)
        else:
            chip = self.get_chip(chip_key)
            chip.config.disable_analog_monitor()
            self.write_configuration(chip_key, Configuration.csa_monitor_select_addresses)
        return

    def enable_testpulse(self, chip_key, channel_list, start_dac=255):
        '''
        Prepare chip for pulsing - enable testpulser and set a starting dac value for
        specified chip/channel
        '''
        chip = self.get_chip(chip_key)
        chip.config.disable_testpulse()
        chip.config.enable_testpulse(channel_list)
        chip.config.csa_testpulse_dac_amplitude = start_dac
        self.write_configuration(chip_key, Configuration.csa_testpulse_enable_addresses +
                                 [Configuration.csa_testpulse_dac_amplitude_address])
        return

    def issue_testpulse(self, chip_key, pulse_dac, min_dac=0):
        '''
        Reduce the testpulser dac by pulse_dac and write_read to chip for 0.1s
        '''
        chip = self.get_chip(chip_key)
        chip.config.csa_testpulse_dac_amplitude -= pulse_dac
        if chip.config.csa_testpulse_dac_amplitude < min_dac:
            raise ValueError('Minimum DAC exceeded')
        self.write_configuration(chip_key, [Configuration.csa_testpulse_dac_amplitude_address],
                                 write_read=0.1)
        return self.reads[-1]

    def disable_testpulse(self, chip_key=None, channel_list=range(32)):
        '''
        Disable testpulser for specified chip/channels. If none specified, disable for
        all chips/channels
        '''
        if chip_key is None:
            for chip_key in self.chips.keys():
                self.disable_testpulse(chip_key=chip_key, channel_list=channel_list)
        else:
            chip = self.get_chip(chip_key)
            chip.config.disable_testpulse(channel_list)
            self.write_configuration(chip_key, Configuration.csa_testpulse_enable_addresses)
        return

    def disable(self, chip_key=None, channel_list=range(32)):
        '''
        Update channel mask to disable specified chips/channels. If none specified,
        disable all chips/channels
        '''
        if chip_key is None:
            for chip_key in self.chips.keys():
                self.disable(chip_key=chip_key, channel_list=channel_list)
        else:
            chip = self.get_chip(chip_key)
            chip.config.disable_channels(channel_list)
            self.write_configuration(chip_key, Configuration.channel_mask_addresses)

    def enable(self, chip_key=None, channel_list=range(32)):
        '''
        Update channel mask to enable specified chips/channels. If none specified,
        enable all chips/channels
        '''
        if chip_key is None:
            for chip_key in self.chips.keys():
                self.enable(chip_key=chip_key, channel_list=channel_list)
        else:
            chip = self.get_chip(chip_key)
            chip.config.enable_channels(channel_list)
            self.write_configuration(chip_key, Configuration.channel_mask_addresses)

    def store_packets(self, packets, data, message):
        '''
        Store the packets in ``self`` and in ``self.chips``

        '''
        new_packets = PacketCollection(packets, data, message)
        new_packets.read_id = self.nreads
        self.nreads += 1
        self.reads.append(new_packets)
        #self.sort_packets(new_packets)

    def sort_packets(self, collection):
        '''
        Sort the packets in ``collection`` into each chip in
        ``self.all_chips`` (if ``self.use_all_chips``) or ``self.chips``
        (otherwise).

        '''
        by_chip_key = collection.by_chip_key()
        for chip_key in by_chip_key.keys():
            if chip_key in self.chips.keys():
                chip = self.get_chip(chip_key)
                chip.reads.append(by_chip_key[chip_key])
            elif not self._test_mode:
                print('Warning chip key {} not in chips.'.format(chip_key))

    def save_output(self, filename, message):
        '''Save the data read by each chip to the specified file.'''
        data = {}
        data['reads'] = [collection.to_dict() for collection in self.reads]
        data['chips'] = [repr(chip) for chip in self.chips.values()]
        data['message'] = message
        with open(filename, 'w') as outfile:
            json.dump(data, outfile, indent=4,
                    separators=(',',':'), sort_keys=True)

class Packet(object):
    '''
    A single 54-bit LArPix UART data packet.

    LArPix Packet objects have attributes for inspecting and modifying
    the contents of the packet.

    Internally, packets are represented as an array of bits, and the
    different attributes use Python "properties" to seamlessly convert
    between the bits representation and a more intuitive integer
    representation. The bits representation can be inspected with the
    ``bits`` attribute.

    Packet objects do not restrict you from adjusting an attribute for an
    inappropriate packet type. For example, you can create a data packet and
    then set ``packet.register_address = 5``. This will adjust the packet
    bits corresponding to a configuration packet's "register\_address"
    region, which is probably not what you want for your data packet.

    Packets have a parity bit which enforces odd parity, i.e. the sum of
    all the individual bits in a packet must be an odd number. The parity
    bit can be accessed as above using the ``parity_bit_value`` attribute.
    The correct parity bit can be computed using ``compute_parity()``,
    and the validity of a packet's parity can be checked using
    ``has_valid_parity()``. When constructing a new packet, the correct
    parity bit can be assigned using ``assign_parity()``.

    Individual packets can be printed to show a human-readable
    interpretation of the packet contents. The printed version adjusts its
    output based on the packet type, so a data packet will show the data
    word, timestamp, etc., while a configuration packet will show the register
    address and register data.

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

    DATA_PACKET = bitarray('00')
    TEST_PACKET = bitarray('01')
    CONFIG_WRITE_PACKET = bitarray('10')
    CONFIG_READ_PACKET = bitarray('11')
    _bit_padding = bitarray('00')

    def __init__(self, bytestream=None):
        if bytestream is None:
            self.bits = bitarray(Packet.size)
            self.bits.setall(False)
            return
        elif len(bytestream) == Packet.num_bytes:
            # Parse the bytestream. Remember that bytestream[0] goes at
            # the 'end' of the BitArray
            reversed_bytestream = bytestream[::-1]
            self.bits = bitarray()
            self.bits.frombytes(reversed_bytestream)
            # Get rid of the padding (now at the beginning of the
            # bitstream because of the reverse order)
            self.bits.pop(0)
            self.bits.pop(0)
        else:
            raise ValueError('Invalid number of bytes: %s' %
                    len(bytestream))

    def __eq__(self, other):
        return self.bits == other.bits

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        string = '[ '
        string += 'Chip key: {} | '.format(self.chip_key)
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
        '''
        Construct the bytes that make up the packet.

        Byte 0 is the first byte that would be sent out and contains the
        first 8 bits of the packet (i.e. packet type and part of the
        chip ID).

        *Note*: The internal bits representation of the packet has a
        different endian-ness compared to the output of this method.

        '''
        # Here's the only other place we have to deal with the
        # endianness issue by reversing the order
        padded_output = self._bit_padding + self.bits
        bytes_output = padded_output.tobytes()
        return bytes_output[::-1]

    def export(self):
        '''Return a dict representation of this Packet.'''
        type_map = {
                self.TEST_PACKET.to01(): 'test',
                self.DATA_PACKET.to01(): 'data',
                self.CONFIG_WRITE_PACKET.to01(): 'config write',
                self.CONFIG_READ_PACKET.to01(): 'config read'
                }
        d = {}
        d['chip_key'] = self.chip_key
        d['bits'] = self.bits.to01()
        d['type'] = type_map[self.packet_type.to01()]
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
    def chip_key(self):
        try:
            return self._chip_key
        except AttributeError:
            return None

    @chip_key.setter
    def chip_key(self, value):
        self._chip_key = value

    @property
    def packet_type(self):
        return self.bits[Packet.packet_type_bits]

    @packet_type.setter
    def packet_type(self, value):
        self.bits[Packet.packet_type_bits] = bah.fromuint(value,
                Packet.packet_type_bits)

    @property
    def chipid(self):
        return bah.touint(self.bits[Packet.chipid_bits])

    @chipid.setter
    def chipid(self, value):
        self.bits[Packet.chipid_bits] = bah.fromuint(value,
                Packet.chipid_bits)

    @property
    def parity_bit_value(self):
        return int(self.bits[Packet.parity_bit])

    @parity_bit_value.setter
    def parity_bit_value(self, value):
        self.bits[Packet.parity_bit] = bool(value)

    def compute_parity(self):
        return 1 - (self.bits[Packet.parity_calc_bits].count(True) % 2)

    def assign_parity(self):
        self.parity_bit_value = self.compute_parity()

    def has_valid_parity(self):
        return self.parity_bit_value == self.compute_parity()

    @property
    def channel_id(self):
        return bah.touint(self.bits[Packet.channel_id_bits])

    @channel_id.setter
    def channel_id(self, value):
        self.bits[Packet.channel_id_bits] = bah.fromuint(value,
                Packet.channel_id_bits)

    @property
    def timestamp(self):
        return bah.touint(self.bits[Packet.timestamp_bits])

    @timestamp.setter
    def timestamp(self, value):
        self.bits[Packet.timestamp_bits] = bah.fromuint(value,
                Packet.timestamp_bits)

    @property
    def dataword(self):
        ostensible_value = bah.touint(self.bits[Packet.dataword_bits])
        # TODO fix in LArPix v2
        return ostensible_value - (ostensible_value % 2)

    @dataword.setter
    def dataword(self, value):
        self.bits[Packet.dataword_bits] = bah.fromuint(value,
                Packet.dataword_bits)

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
        return bah.touint(self.bits[Packet.register_address_bits])

    @register_address.setter
    def register_address(self, value):
        self.bits[Packet.register_address_bits] = bah.fromuint(value,
                Packet.register_address_bits)

    @property
    def register_data(self):
        return bah.touint(self.bits[Packet.register_data_bits])

    @register_data.setter
    def register_data(self, value):
        self.bits[Packet.register_data_bits] = bah.fromuint(value,
                Packet.register_data_bits)

    @property
    def test_counter(self):
        return bah.touint(self.bits[Packet.test_counter_bits_15_12] +
                self.bits[Packet.test_counter_bits_11_0])

    @test_counter.setter
    def test_counter(self, value):
        allbits = bah.fromuint(value, 16)
        self.bits[Packet.test_counter_bits_15_12] = (
            bah.fromuint(allbits[:4], Packet.test_counter_bits_15_12))
        self.bits[Packet.test_counter_bits_11_0] = (
            bah.fromuint(allbits[4:], Packet.test_counter_bits_11_0))

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
    def __init__(self, packets, bytestream=None, message='',
            read_id=None, skipped=None):
        self.packets = packets
        self.bytestream = bytestream
        self.skipped = skipped
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
            items.read_id = self.read_id
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
            return [' '.join(p.bits.to01()[i:i+8] for i in
                range(0, Packet.size, 8)) for p in self.packets[key]]
        else:
            return ' '.join(self.packets[key].bits.to01()[i:i+8] for i in
                    range(0, Packet.size, 8))

    def to_dict(self):
        '''
        Export the information in this PacketCollection to a dict.

        '''
        d = {}
        d['packets'] = [packet.export() for packet in self.packets]
        d['id'] = id(self)
        d['parent'] = 'None' if self.parent is None else id(self.parent)
        d['message'] = str(self.message)
        d['read_id'] = 'None' if self.read_id is None else self.read_id
        d['bytestream'] = ('None' if self.bytestream is None else
                self.bytestream.decode('raw_unicode_escape'))
        return d

    def from_dict(self, d):
        '''
        Load the information in the dict into this PacketCollection.

        '''
        self.message = d['message']
        self.read_id = d['read_id']
        self.bytestream = d['bytestream'].encode('raw_unicode_escape')
        self.parent = None
        self.packets = []
        for p in d['packets']:
            bits = p['bits']
            packet = Packet()
            packet.bits = bitarray(bits)
            self.packets.append(packet)

    def extract(self, attr, **selection):
        '''
        Extract the given attribute from packets specified by selection
        and return a list.

        Any key used in Packet.export is a valid attribute or selection:

        - all packets:
             - chip_key
             - bits
             - type (data, test, config read, config write)
             - chipid
             - parity
             - valid_parity
        - data packets:
             - channel
             - timestamp
             - adc_counts
             - fifo_half
             - fifo_full
        - test packets:
             - counter
        - config packets:
             - register
             - value

        Usage:

        >>> # Return a list of adc counts from any data packets
        >>> adc_data = collection.extract('adc_counts')
        >>> # Return a list of timestamps from chip 2 data
        >>> timestamps = collection.extract('timestamp', chipid=2)
        >>> # Return the most recently read global threshold from chip 5
        >>> threshold = collection.extract('value', register=32, type='config read', chip=5)[-1]

        '''
        values = []
        for p in self.packets:
            try:
                d = p.export()
                if all( d[key] == value for key, value in selection.items()):
                    values.append(d[attr])
            except KeyError:
                continue
        return values

    def origin(self):
        '''
        Return the original PacketCollection that this PacketCollection
        derives from.

        '''
        child = self
        parent = self.parent
        max_generations = 100  # to prevent infinite loops
        i = 0
        while parent is not None and i < max_generations:
            # Move up the family tree one generation
            child = parent
            parent = parent.parent
            i += 1
        if parent is None:
            return child
        else:
            raise ValueError('Reached limit on generations: %d' %
                    max_generations)

    def with_chip_key(self, chip_key):
        '''
        Return packets with the specified chip key.

        '''
        return [packet for packet in self.packets if packet.chip_key == chip_key]

    def by_chip_key(self):
        '''
        Return a dict of { chipid: PacketCollection }.

        '''
        chip_groups = {}
        for packet in self.packets:
            # append packet to list if list exists, else append to empty
            # list as a default
            chip_groups.setdefault(packet.chip_key, []).append(packet)
        to_return = {}
        for chip_key in chip_groups:
            new_collection = PacketCollection(chip_groups[chip_key])
            new_collection.message = self.message + ' | chip {}'.format(chip_key)
            new_collection.read_id = self.read_id
            new_collection.parent = self
            to_return[chipid] = new_collection
        return to_return

    def with_chipid(self, chipid):
        '''
        Return packets with the specified chip ID.

        '''
        return [packet for packet in self.packets if packet.chipid == chipid]

    def by_chipid(self):
        '''
        Return a dict of { chipid: PacketCollection }.

        '''
        chip_groups = {}
        for packet in self.packets:
            # append packet to list if list exists, else append to empty
            # list as a default
            chip_groups.setdefault(packet.chipid, []).append(packet)
        to_return = {}
        for chipid in chip_groups:
            new_collection = PacketCollection(chip_groups[chipid])
            new_collection.message = self.message + ' | chip %s' % chipid
            new_collection.read_id = self.read_id
            new_collection.parent = self
            to_return[chipid] = new_collection
        return to_return

