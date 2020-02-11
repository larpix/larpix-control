from bitarray import bitarray
import os
import errno

from .. import bitarrayhelper as bah
from .. import configs
from . import BaseConfiguration, _Smart_List

class Configuration_v1(BaseConfiguration):
    '''
    Represents the desired configuration state of a LArPix v1 chip.

    '''

    asic_version = 1
    default_configuration_file = 'chip/default.json'
    num_registers = 63
    num_channels = 32
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
        super(Configuration_v1, self).__init__()

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

    @property
    def pixel_trim_thresholds(self):
        return self._pixel_trim_thresholds

    @pixel_trim_thresholds.setter
    def pixel_trim_thresholds(self, values):
        low = 0
        high = 31
        if not (type(values) == list or type(values) == _Smart_List):
            raise ValueError("pixel_trim_threshold is not list")
        if not len(values) == Configuration_v1.num_channels:
            raise ValueError("pixel_trim_threshold length is not %d" % Configuration_v1.num_channels)
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
        if not len(values) == Configuration_v1.num_channels:
            raise ValueError("csa_bypass_select length is not %d" % Configuration_v1.num_channels)
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
        if not len(values) == Configuration_v1.num_channels:
            raise ValueError("csa_monitor_select length is not %d" % Configuration_v1.num_channels)
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
        if not len(values) == Configuration_v1.num_channels:
            raise ValueError("csa_testpulse_enable length is not %d" % Configuration_v1.num_channels)
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
        valid_values = [Configuration_v1.TEST_OFF, Configuration_v1.TEST_UART,
                        Configuration_v1.TEST_FIFO]
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
        if not len(values) == Configuration_v1.num_channels:
            raise ValueError("channel_mask length is not %d" % Configuration_v1.num_channels)
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
        if not len(values) == Configuration_v1.num_channels:
            raise ValueError("external_trigger_mask length is not %d" % Configuration_v1.num_channels)
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
            list_of_channels = range(Configuration_v1.num_channels)
        for channel in list_of_channels:
            self.channel_mask[channel] = 0

    def disable_channels(self, list_of_channels=None):
        '''
        Shortcut for changing the channel mask for the given channels
        to "disable" (i.e. 1).

        '''
        if list_of_channels is None:
            list_of_channels = range(Configuration_v1.num_channels)
        for channel in list_of_channels:
            self.channel_mask[channel] = 1

    def enable_external_trigger(self, list_of_channels=None):
        '''
        Shortcut for enabling the external trigger functionality for the
        given channels. (I.e. disabling the mask.)

        '''
        if list_of_channels is None:
            list_of_channels = range(Configuration_v1.num_channels)
        for channel in list_of_channels:
            self.external_trigger_mask[channel] = 0

    def disable_external_trigger(self, list_of_channels=None):
        '''
        Shortcut for disabling the external trigger functionality for
        the given channels. (I.e. enabling the mask.)

        '''
        if list_of_channels is None:
            list_of_channels = range(Configuration_v1.num_channels)
        for channel in list_of_channels:
            self.external_trigger_mask[channel] = 1

    def enable_testpulse(self, list_of_channels=None):
        '''
        Shortcut for enabling the test pulser for the given channels.

        '''
        if list_of_channels is None:
            list_of_channels = range(Configuration_v1.num_channels)
        for channel in list_of_channels:
            self.csa_testpulse_enable[channel] = 0

    def disable_testpulse(self, list_of_channels=None):
        '''
        Shortcut for disabling the test pulser for the given channels.

        '''
        if list_of_channels is None:
            list_of_channels = range(Configuration_v1.num_channels)
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
        self.csa_monitor_select = [0] * Configuration_v1.num_channels

    def all_data(self, **kwargs):
        bits = []
        num_channels = Configuration_v1.num_channels
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

    def from_dict_registers(self, d, **kwargs):
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
