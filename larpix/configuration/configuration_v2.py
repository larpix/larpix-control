from bitarray import bitarray
import os
import errno
import functools
from collections import OrderedDict

from .. import bitarrayhelper as bah
from .. import configs
from . import BaseConfiguration, _Smart_List

class Configuration_v2(BaseConfiguration):
    '''
    Represents the desired configuration state of a LArPix v2 chip.

    Each register name is available as its own attribute for inspecting and
    setting the value of the corresponding register.

    Certain configuration values are set channel-by-channel. These are
    represented by a list of values. For example:

        >>> conf.pixel_trim_dac[2:5]
        [16, 16, 16]
        >>> conf.channel_mask[20] = 1
        >>> conf.external_trigger_mask = [0] * 64

    Additionally, other configuration values take up more than or less
    than one complete register. These are still set by referencing the
    appropriate name. For example, ``cross_trigger_mode`` shares a
    register with a few other values, and adjusting the value of the
    ``cross_trigger_mode`` attribute will leave the other values
    unchanged.

    Each register name can cover more than one 'physical' register depending on
    the size of the data it holds. You can see which physical registers a
    given register name corresponds to by using the `register_map` attribute, e.g.::

        >>> conf.register_map['digital_threshold']  # 64 registers, 1 per channel
        range(173, 237)
        >>> conf.register_map['enable_dynamic_reset']  # Register 170
        range(170, 171)
        >>> conf.register_map['enable_min_delta_adc']  # Shares register 170
        range(170, 171)

    '''

    asic_version = 2
    default_configuration_file = 'chip/default_v2.json'
    num_registers = 237
    num_bits = 1896
    num_channels = 64
    # Additional class properties regarding configuration registers are set at the end of the file.

    _endian = 'little'

    def __init__(self):
        # Note: properties, getters and setters are constructed after this class definition at the bottom of the file.
        super(Configuration_v2, self).__init__()
        return

    def all_data(self, endian='little'):
        bits = []
        for register_name in self.register_names:
            register_data =  getattr(self, register_name+'_data')
            for register_addr, register_bits in register_data:
                if len(bits) == register_addr:
                    if endian[0] == 'l':
                        bits += [register_bits]
                    else:
                        bits += [register_bits[::-1]]
        return bits

    def from_dict_registers(self, d, endian='little'):
        '''
        Load in the configuration specified by a dict of (register,
        value) pairs.

        '''
        for address, value in d.items():
            register_names = self.register_map_inv[address]
            for register_name in register_names:
                setattr(self, register_names[0] + '_data', (address, bah.fromuint(value,8,endian=endian)))
        return

    def _is_register_value_pair(self, item):
        '''
        Helper function to determine if item is a register, bitarray pair

        '''
        if isinstance(item, tuple) and len(item) == 2 and \
                isinstance(item[0], int) and isinstance(item[1], bitarray)\
                and len(item[1]) == 8 and item[0] >= 0 and item[0] < self.num_registers:
            return True
        return False

### Stuff for generating the v2 configuration properties

## Getter function formulas
#
def _basic_getter(register_name):
    '''
    Function formula for getting a named register

    '''
    def basic_getter_func(self):
        return getattr(self, '_'+register_name)
    return basic_getter_func
# /Getter function formulas

## Setter function formulas
#
def _basic_setter(register_name):
    '''
    Function formula for setting a named register

    '''
    def basic_setter_func(self, value):
        setattr(self, '_'+register_name, value)
    return basic_setter_func

def _list_setter(register_name, min_value, max_value):
    '''
    Function formula for setting a named register

    '''
    def list_setter_func(self, value):
        setattr(self, '_'+register_name, _Smart_List(value, min_value, max_value))
    return list_setter_func

# /Setter function formulas

## Data getter function formulas
#
def _basic_data_getter(register_name):
    '''
    Function formula for getting a "simple" register's data
    A simple register has a one-to-many relationship between the register
    name and register addresses.

    Returns a list of register_addr, bitarray pairs

    '''
    def basic_data_getter_func(self):
        register_range = self.register_map[register_name]
        value = getattr(self, register_name)
        all_data = bah.fromuint(value, 8*(register_range[-1]-register_range[0]+1), endian=self._endian)
        return_data = [(register, all_data[idx*8:idx*8+8]) for idx, register in enumerate(register_range)]
        return return_data
    return basic_data_getter_func

def _list_data_getter(register_name, n_bits):
    '''
    Function formula for getting a list-like register's data
    A list-like register contains repeated functionality every ``n_bits``
    over 1 or more register addresses.

    Returns a list of register_addr, bitarray pairs

    '''
    def list_data_getter_func(self):
        register_range = self.register_map[register_name]
        values = getattr(self, register_name)
        all_data = bitarray([])
        for value in values:
            all_data += bah.fromuint(value, n_bits, endian=self._endian)
        if len(all_data) < 8:
            all_data += bitarray([0]*(8-len(all_data)%8)) # pad up to full register
        return [(register_addr, all_data[idx*8:idx*8+8]) for idx, register_addr in enumerate(register_range)]
    return list_data_getter_func

def _compound_data_getter(registers):
    '''
    Function formula for getting a compound register's data
    A compound register has a one-to-many mapping of register address to
    register names.
    ``registers`` should be the register names contained within the
    register address (in order of lowest bit to highest)

    Returns a list of register, bitarray pairs

    '''
    def compound_data_getter_func(self):
        bits = bitarray([0]*8)
        for register_name in registers:
            start_bit, end_bit = self.bit_map[register_name]
            bits[start_bit%8:end_bit-start_bit+start_bit%8] = bah.fromuint(getattr(self, register_name), end_bit-start_bit, endian=self._endian)
        return [(self.register_map[registers[0]][0], bits)]
    return compound_data_getter_func

def _compound_list_data_getter(registers, n_bits):
    '''
    Function formula for getting a compound list register's data
    A compound list register has a one-to-many mapping of register
    addresses to register names, but with repeating functionality within
    each register name of size ``n_bits``. For example, you might store two
    1bit arrays of length 2 within the same register address.
    ``registers`` should be the register names contained within the
    register address (in order of lowest bit to highest)

    Returns a list of register, bitarray pairs

    '''
    def compound_list_data_getter_func(self):
        bits = bitarray([])
        for register_name in registers:
            values = getattr(self, register_name)
            for value in values:
                bits += bah.fromuint(value, n_bits, endian=self._endian)
        if len(bits)%8 != 0:
            bits += bitarray([0]*(8-len(bits)%8)) # pad up to full register
        return [(self.register_map[registers[0]][0], bits)]
    return compound_list_data_getter_func
# /Data getter function formulas

## Data setter function formulas
#
def _basic_data_setter(register_name):
    '''
    Function formula for setting a simple register's data
    Data can be specified as a register, bitarray pair or via a full-length
    bitarray

    '''
    def basic_data_setter_func(self, value):
        if self._is_register_value_pair(value):
            # regenerate complete list of bits and set
            set_register, set_bits = value
            data = getattr(self, register_name+'_data')
            all_bits = bitarray([])
            for register, bits in data:
                if register == set_register:
                    all_bits += set_bits
                else:
                    all_bits += bits
            start_bit, end_bit = self.bit_map[register_name]
            setattr(self, register_name+'_data', all_bits[start_bit%8:end_bit-start_bit+start_bit%8])
        else:
            # use all bits to set values
            bits = value
            value = bah.touint(bits, endian=self._endian)
            setattr(self, register_name, value)
    return basic_data_setter_func

def _list_data_setter(register_name, n_bits, min_value, max_value):
    '''
    Function formula for setting a list-like register's data
    A list-like register contains repeated functionality every ``n_bits``
    over 1 or more register addresses.
    Data can be specified as a register, bitarray pair or via a full-length
    bitarray

    '''
    def list_data_setter_func(self, values):
        if self._is_register_value_pair(values):
            # regenerate complete list of bits and set
            set_register, set_bits = values
            data = getattr(self, register_name+'_data')
            all_bits = bitarray([])
            for register, bits in data:
                if register == set_register:
                    all_bits += set_bits
                else:
                    all_bits += bits
            start_bit, end_bit = self.bit_map[register_name]
            setattr(self, register_name+'_data', all_bits[start_bit%8:end_bit-start_bit+start_bit%8])
        else:
            # use all bits to set values
            bits = values
            item_values = [bah.touint(bits[idx:idx+n_bits], endian=self._endian) for idx in range(0, len(bits), n_bits)]
            setattr(self, register_name, _Smart_List(item_values, min_value, max_value))
    return list_data_setter_func

def _compound_data_setter(registers, register_name):
    '''
    Function formula for setting a compound register's data
    A compound register has a one-to-many mapping of register address to
    register names.
    ``registers`` should be the register names contained within the
    register address (in order of lowest bit to highest)
    Data can be specified as a register, bitarray pair or via a full-length
    bitarray

    '''
    def compound_data_setter_func(self, value):
        if self._is_register_value_pair(value):
            set_register_addr, set_bits = value
            for register in registers:
                start_bit, end_bit = self.bit_map[register]
                setattr(self, register + '_data', set_bits[start_bit%8:end_bit-start_bit+start_bit%8])
        else:
            # use all bits to set values
            set_bits = value
            setattr(self, register_name, bah.touint(set_bits, endian=self._endian))
    return compound_data_setter_func

def _compound_list_data_setter(registers, register_name, n_bits, min_value, max_value):
    '''
    Function formula for setting a compound list register's data
    A compound list register has a one-to-many mapping of register address to
    register names with repeating functionality every ``n_bits``.
    ``registers`` should be the register names contained within the
    register address (in order of lowest bit to highest)
    Data can be specified as a register, bitarray pair or via a full-length
    bitarray

    '''
    def compound_list_data_setter_func(self, value):
        if self._is_register_value_pair(value):
            set_register_addr, set_bits = value
            for register in registers:
                start_bit, end_bit = self.bit_map[register]
                setattr(self, register + '_data', set_bits[start_bit%8:end_bit-start_bit+start_bit%8])
        else:
            set_bits = value
            values = [bah.touint(set_bits[idx:idx+n_bits], endian=self._endian) for idx in range(0,len(set_bits),n_bits)]
            setattr(self, register_name, _Smart_List(values, min_value, max_value))
    return compound_list_data_setter_func
# /Data setter function formulas

## Value validation function formulas
#
def _value_validator(value_types, min_value, max_value):
    '''
    Function formula for validating a register that contains a single value
    Accepts values of types ``value_types``, greater than  ``min_value``,
    and less than ``max_value``.

    '''
    def value_validator(func):
        @functools.wraps(func)
        def value_validated_func(self, value):
            if not isinstance(value, value_types):
                raise TypeError('value must be of type {}'.format(value_types))
            if value > max_value or value < min_value:
                raise ValueError('value must be between {} and {}'.format(min_value,max_value))
            return func(self, value)
        return value_validated_func
    return value_validator

def _list_validator(value_types, min_value, max_value, n_values):
    '''
    Function formula for validating a register that contains list-like data
    Accepts lists of length ``n_values`` with objects with types
    ``value_types``, greater than  ``min_value``, and less than ``max_value``.

    '''
    def list_validator(func):
        @functools.wraps(func)
        def list_validated_func(self, values):
            if not isinstance(values, (list, _Smart_List, tuple)):
                raise TypeError('argument must be a list or tuple')
            if len(values) != n_values:
                raise ValueError('length of list must be {}'.format(n_values))
            if any([not isinstance(value, value_types) for value in values]):
                raise TypeError('values must be of type {}'.format(value_types))
            if any([value > max_value or value < min_value for value in values]):
                raise ValueError('values must be between {} and {}'.format(min_value,max_value))
            return func(self, values)
        return list_validated_func
    return list_validator

def _data_validator(register_name):
    '''
    Function formula for validating setting a register via a register
    address, bitarray pair or direct bitarray

    '''
    def data_validator(func):
        @functools.wraps(func)
        def data_validated_func(self, value):
            if self._is_register_value_pair(value):
                register_addr, bits  = value
                if register_addr < self.register_map[register_name][0] \
                or register_addr > self.register_map[register_name][-1] \
                or len(bits) != 8:
                    raise ValueError('invalid register, value pair {}'
                        ' for register {}'.format(value,register_name))
                return func(self, value)
            elif isinstance(value, bitarray):
                bits = value
                start_bit, stop_bit = self.bit_map[register_name]
                if len(bits) != stop_bit - start_bit:
                    raise ValueError('invalid bitarray {}'
                        ' for register {}'.format(value,register_name))
                return func(self, value)
            else:
                raise TypeError('{} data must be assigned with '
                    'register, value pair or bitarray'.format(register_name))
        return data_validated_func
    return data_validator
# /Value validation function formulas

## Property function formulas
#
def _basic_property(name, registers, bits, types, min, max):
    docstring = '''
        simple value property

        registers: ``{}``

        valid types: ``{}``

        value range: ``{}`` to ``{}``
        '''.format(registers, types, min, max)
    return (
        property(
            _basic_getter(name),
            _value_validator(types,min,max)(
                _basic_setter(name)),
            doc=docstring),
        property(
            _basic_data_getter(name),
            _data_validator(name)(
                _basic_data_setter(name))))

def _list_property(name, registers, bits, types, min, max, length, n_bits):
    docstring = '''
        list-like property

        list length: ``{}``

        registers: ``{}``

        element valid types: ``{}``

        element value range: ``{}`` to ``{}``
        '''.format(length, registers, types, min, max)
    return (
        property(
            _basic_getter(name),
            _list_validator(types,min,max,length)(
                _list_setter(name,min,max)),
            doc=docstring),
        property(
            _list_data_getter(name,n_bits),
            _data_validator(name)(
                _list_data_setter(name,n_bits,min,max))))

def _compound_property(name, registers, bits, names, types, min, max):
    docstring = '''
        compound property

        registers: ``{}``

        bits: ``{}``

        valid types: ``{}``

        value range: ``{}`` to ``{}``

        shares a register with: ``{}``
        '''.format(registers, [bit%8 for bit in bits], types, min, max, [n for n in names if not n == name])
    return (
        property(
            _basic_getter(name),
            _value_validator(types,min,max)(
                _basic_setter(name)),
            doc=docstring
            ),
        property(
            _compound_data_getter(names),
            _data_validator(name)(
                _compound_data_setter(names, name))))

def _compound_list_property(name, registers, bits, names, types, min, max, length, n_bits):
    docstring = '''
        compound list-like property

        list length: ``{}``

        registers: ``{}``

        element valid types: ``{}``

        element value range: ``{}`` to ``{}``

        shares a register with: ``{}``
        '''.format(length, registers, types, min, max, [n for n in names if not n == name])
    return (
        property(
            _basic_getter(name),
            _list_validator(types,min,max,length)(
                _list_setter(name,min,max)),
            doc=docstring
            ),
        property(
            _compound_list_data_getter(names,n_bits),
            _data_validator(name)(
                _compound_list_data_setter(names,name,n_bits,min,max))))
# /Property function formulas

## Set up property info
#
_property_configuration = OrderedDict([
        ('pixel_trim_dac',
            (_list_property, (int, 0, 31, Configuration_v2.num_channels, 8), (0,512))),
        ('threshold_global',
            (_basic_property, (int, 0, 255), (512, 520))),
        ('csa_gain',
            (_compound_property, (['csa_gain', 'csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (520,521))),
        ('csa_bypass_enable',
            (_compound_property, (['csa_gain', 'csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (521,522))),
        ('bypass_caps_en',
            (_compound_property, (['csa_gain', 'csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (522,523))),
        ('csa_enable',
            (_list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (528, 592))),
        ('ibias_tdac',
            (_basic_property, (int, 0, 15), (592, 596))),
        ('ibias_comp',
            (_basic_property, (int, 0, 15), (600, 604))),
        ('ibias_buffer',
            (_basic_property, (int, 0, 15), (608, 612))),
        ('ibias_csa',
            (_basic_property, (int, 0, 15), (616, 620))),
        ('ibias_vref_buffer',
            (_basic_property, (int, 0, 15), (624, 628))),
        ('ibias_vcm_buffer',
            (_basic_property, (int, 0, 15), (632, 636))),
        ('ibias_tpulse',
            (_basic_property, (int, 0, 15), (640, 644))),
        ('ref_current_trim',
            (_compound_property, (['ref_current_trim','override_ref','ref_kickstart'], int, 0, 31), (648, 653))),
        ('override_ref',
            (_compound_property, (['ref_current_trim','override_ref','ref_kickstart'], (int,bool), 0, 1), (653, 654))),
        ('ref_kickstart',
            (_compound_property, (['ref_current_trim','override_ref','ref_kickstart'], (int,bool), 0, 1), (654, 655))),
        ('vref_dac',
            (_basic_property, (int, 0, 255), (656, 664))),
        ('vcm_dac',
            (_basic_property, (int, 0, 255), (664,672))),
        ('csa_bypass_select',
            (_list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (672,736))),
        ('csa_monitor_select',
            (_list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (736,800))),
        ('csa_testpulse_enable',
            (_list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (800,864))),
        ('csa_testpulse_dac',
            (_basic_property, (int, 0, 255), (864,872))),
        ('current_monitor_bank0',
            (_list_property, ((int,bool), 0, 1, 4, 1), (872,876))),
        ('current_monitor_bank1',
            (_list_property, ((int,bool), 0, 1, 4, 1), (880,884))),
        ('current_monitor_bank2',
            (_list_property, ((int,bool), 0, 1, 4, 1), (888,892))),
        ('current_monitor_bank3',
            (_list_property, ((int,bool), 0, 1, 4, 1), (896,900))),
        ('voltage_monitor_bank0',
            (_list_property, ((int,bool), 0, 1, 3, 1), (904,907))),
        ('voltage_monitor_bank1',
            (_list_property, ((int,bool), 0, 1, 3, 1), (912,915))),
        ('voltage_monitor_bank2',
            (_list_property, ((int,bool), 0, 1, 3, 1), (920,923))),
        ('voltage_monitor_bank3',
            (_list_property, ((int,bool), 0, 1, 3, 1), (928,931))),
        ('voltage_monitor_refgen',
            (_list_property, ((int,bool), 0, 1, 8, 1), (936,944))),
        ('digital_monitor_enable',
            (_compound_property, (['digital_monitor_enable','digital_monitor_select'], (int,bool), 0, 1), (944,945))),
        ('digital_monitor_select',
            (_compound_property, (['digital_monitor_enable','digital_monitor_select'], (int,bool), 0, 10), (945,949))),
        ('digital_monitor_chan',
            (_basic_property, (int, 0, 63), (952,958))),
        ('slope_control0',
            (_compound_property, (['slope_control0', 'slope_control1'], int, 0, 15), (960,964))),
        ('slope_control1',
            (_compound_property, (['slope_control0', 'slope_control1'], int, 0, 15), (964,968))),
        ('slope_control2',
            (_compound_property, (['slope_control2', 'slope_control3'], int, 0, 15), (968,972))),
        ('slope_control3',
            (_compound_property, (['slope_control2', 'slope_control3'], int, 0, 15), (972,976))),
        ('chip_id',
            (_basic_property, (int, 0, 255), (976,984))),
        ('load_config_defaults',
            (_compound_property, (['load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl'], (int,bool), 0, 1), (985,986))),
        ('enable_fifo_diagnostics',
            (_compound_property, (['load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl'], (int,bool), 0, 1), (986,987))),
        ('clk_ctrl',
            (_compound_property, (['load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl'], (int), 0, 2), (987,989))),
        ('enable_miso_upstream',
            (_list_property, ((int,bool), 0, 1, 4, 1), (992,996))),
        ('enable_miso_downstream',
            (_compound_list_property, (['enable_miso_downstream', 'enable_miso_differential'], (int,bool), 0, 1, 4, 1), (1000,1004))),
        ('enable_miso_differential',
            (_compound_list_property, (['enable_miso_downstream', 'enable_miso_differential'], (int,bool), 0, 1, 4, 1), (1004,1008))),
        ('enable_mosi',
            (_list_property, ((int,bool), 0, 1, 4, 1), (1008,1012))),
        ('test_mode_uart0',
            (_compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 4), (1016,1018))),
        ('test_mode_uart1',
            (_compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 4), (1018,1020))),
        ('test_mode_uart2',
            (_compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 4), (1020,1022))),
        ('test_mode_uart3',
            (_compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 4), (1022,1024))),
        ('enable_cross_trigger',
            (_compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1024,1025))),
        ('enable_periodic_reset',
            (_compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1025,1026))),
        ('enable_rolling_periodic_reset',
            (_compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1026,1027))),
        ('enable_periodic_trigger',
            (_compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1027,1028))),
        ('enable_rolling_periodic_trigger',
            (_compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1028,1029))),
        ('enable_periodic_trigger_veto',
            (_compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1029,1030))),
        ('enable_hit_veto',
            (_compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1030,1031))),
        ('adc_hold_delay',
            (_basic_property, (int, 0, 15), (1032,1036))),
        ('adc_burst_length',
            (_basic_property, (int, 0, 255), (1040,1048))),
        ('channel_mask',
            (_list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (1048,1112))),
        ('external_trigger_mask',
            (_list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (1112,1176))),
        ('cross_trigger_mask',
            (_list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (1176,1240))),
        ('periodic_trigger_mask',
            (_list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (1240,1304))),
        ('periodic_reset_cycles',
            (_basic_property, (int, 0, 2**24-1), (1304,1328))),
        ('periodic_trigger_cycles',
            (_basic_property, (int, 0, 2**32-1), (1328,1360))),
        ('enable_dynamic_reset',
            (_compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1360,1361))),
        ('enable_min_delta_adc',
            (_compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1361,1362))),
        ('threshold_polarity',
            (_compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1362,1363))),
        ('reset_length',
            (_compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int), 0, 7), (1363,1366))),
        ('mark_first_packet',
            (_compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1366,1367))),
        ('reset_threshold',
            (_basic_property, (int, 0, 255), (1368,1376))),
        ('min_delta_adc',
            (_basic_property, (int, 0, 255), (1376,1384))),
        ('digital_threshold',
            (_list_property, (int, 0, 255, Configuration_v2.num_channels, 8), (1384,1896))),
    ])

# GENERATE THE PROPERTIES!
Configuration_v2.bit_map = OrderedDict()
Configuration_v2.register_map = OrderedDict()
Configuration_v2.register_names = []

def _generate_properties(cls, property_configuration, verbose=False):
    for _name, _prop_config in property_configuration.items():
        _prop_formula = _prop_config[0]
        _formula_args = _prop_config[1]
        _bit_range = _prop_config[2]
        if verbose:
            print('Generate {}.{} using bits {}\n\t{}({}) '.format(cls,_name, _bit_range, _prop_formula, _formula_args))

        # Add to class attributes
        cls.register_names += [_name]
        cls.bit_map[_name] = _bit_range
        cls.register_map[_name] = range(_bit_range[0]//8, max(_bit_range[1]//8,_bit_range[0]//8+1))

        # Create properties
        _prop, _prop_data = _prop_formula(_name, cls.register_map[_name],
            range(*cls.bit_map[_name]), *_formula_args)
        setattr(cls, _name, _prop)
        setattr(cls, _name+'_data', _prop_data)

    # Create a look up table from register address to names
    cls.register_map_inv = OrderedDict()
    for register_name, register_addr_range in cls.register_map.items():
        for register_addr in register_addr_range:
            try:
                cls.register_map_inv[register_addr] += [register_name]
            except KeyError:
                cls.register_map_inv[register_addr] = [register_name]

_generate_properties(Configuration_v2, _property_configuration, verbose=False)



