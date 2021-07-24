from bitarray import bitarray
import os
import errno
import functools
from collections import OrderedDict

from .. import bitarrayhelper as bah
from .. import configs
from . import BaseConfiguration, Configuration_v2, _Smart_List
from . import configuration_v2 as conf_v2


class Configuration_v2b(BaseConfiguration):
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

    asic_version = 'larpix-v2b'
    default_configuration_file = 'chip/default_v2b.json'
    num_registers = 256
    num_bits = 2048

    _endian = 'little'
    # Additional class properties regarding configuration registers are set at the end of the file.

    def __init__(self):
        # Note: properties, getters and setters are constructed after this class definition at the bottom of the file.
        super(Configuration_v2b, self).__init__()
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

    def some_data(self, registers, endian='little'):
        '''
        Fetch register addresses and data from a selected set of registers

        :param registers: list of registers to fetch data for, specified either by register name (str) or register addresses (int)

        :returns: tuple of list of register addresses and list of register data

        '''
        bits = []
        addrs = []
        for register in registers:
            if isinstance(register, int):
                register_name = self.register_map_inv[register][0]
                register_data = getattr(self, register_name+'_data')
            elif isinstance(register, str):
                register_data = getattr(self, register+'_data')
            for register_addr, register_bits in register_data:
                if isinstance(register, int) and register_addr != register:
                    continue
                if endian[0] == 'l':
                    bits += [register_bits]
                    addrs += [register_addr]
                else:
                    bits += [register_bits[::-1]]
                    addrs += [register_addr]
        return addrs, bits

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

## Set up property info
#
_property_configuration = OrderedDict([
        ('pixel_trim_dac',
            (conf_v2._list_property, (int, 0, 31, Configuration_v2.num_channels, 8), (0,512))),
        ('threshold_global',
            (conf_v2._basic_property, (int, 0, 255), (512, 520))),
        ('csa_gain',
            (conf_v2._compound_property, (['csa_gain', 'csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (520,521))),
        ('csa_bypass_enable',
            (conf_v2._compound_property, (['csa_gain', 'csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (521,522))),
        ('bypass_caps_en',
            (conf_v2._compound_property, (['csa_gain', 'csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (522,523))),
        ('csa_enable',
            (conf_v2._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (528, 592))),
        ('ibias_tdac',
            (conf_v2._basic_property, (int, 0, 15), (592, 596))),
        ('ibias_comp',
            (conf_v2._basic_property, (int, 0, 15), (600, 604))),
        ('ibias_buffer',
            (conf_v2._basic_property, (int, 0, 15), (608, 612))),
        ('ibias_csa',
            (conf_v2._basic_property, (int, 0, 15), (616, 620))),
        ('ibias_vref_buffer',
            (conf_v2._basic_property, (int, 0, 15), (624, 628))),
        ('ibias_vcm_buffer',
            (conf_v2._basic_property, (int, 0, 15), (632, 636))),
        ('ibias_tpulse',
            (conf_v2._basic_property, (int, 0, 15), (640, 644))),
        ('ref_current_trim',
            (conf_v2._compound_property, (['ref_current_trim','override_ref','ref_kickstart'], int, 0, 31), (648, 653))),
        ('override_ref',
            (conf_v2._compound_property, (['ref_current_trim','override_ref','ref_kickstart'], (int,bool), 0, 1), (653, 654))),
        ('ref_kickstart',
            (conf_v2._compound_property, (['ref_current_trim','override_ref','ref_kickstart'], (int,bool), 0, 1), (654, 655))),
        ('vref_dac',
            (conf_v2._basic_property, (int, 0, 255), (656, 664))),
        ('vcm_dac',
            (conf_v2._basic_property, (int, 0, 255), (664,672))),
        ('csa_bypass_select',
            (conf_v2._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (672,736))),
        ('csa_monitor_select',
            (conf_v2._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (736,800))),
        ('csa_testpulse_enable',
            (conf_v2._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (800,864))),
        ('csa_testpulse_dac',
            (conf_v2._basic_property, (int, 0, 255), (864,872))),
        ('current_monitor_bank0',
            (conf_v2._list_property, ((int,bool), 0, 1, 4, 1), (872,876))),
        ('current_monitor_bank1',
            (conf_v2._list_property, ((int,bool), 0, 1, 4, 1), (880,884))),
        ('current_monitor_bank2',
            (conf_v2._list_property, ((int,bool), 0, 1, 4, 1), (888,892))),
        ('current_monitor_bank3',
            (conf_v2._list_property, ((int,bool), 0, 1, 4, 1), (896,900))),
        ('voltage_monitor_bank0',
            (conf_v2._list_property, ((int,bool), 0, 1, 3, 1), (904,907))),
        ('voltage_monitor_bank1',
            (conf_v2._list_property, ((int,bool), 0, 1, 3, 1), (912,915))),
        ('voltage_monitor_bank2',
            (conf_v2._list_property, ((int,bool), 0, 1, 3, 1), (920,923))),
        ('voltage_monitor_bank3',
            (conf_v2._list_property, ((int,bool), 0, 1, 3, 1), (928,931))),
        ('voltage_monitor_refgen',
            (conf_v2._list_property, ((int,bool), 0, 1, 8, 1), (936,944))),
        ('digital_monitor_enable',
            (conf_v2._compound_property, (['digital_monitor_enable','digital_monitor_select'], (int,bool), 0, 1), (944,945))),
        ('digital_monitor_select',
            (conf_v2._compound_property, (['digital_monitor_enable','digital_monitor_select'], (int,bool), 0, 10), (945,949))),
        ('digital_monitor_chan',
            (conf_v2._basic_property, (int, 0, 63), (952,958))),
        ('adc_hold_delay',
            (conf_v2._basic_property, (int, 0, 65535), (960, 976))),
        ('chip_id',
            (conf_v2._basic_property, (int, 0, 255), (976, 984))),
        ('enable_tx_dynamic_powerdown',
            (conf_v2._compound_property, (['enable_tx_dynamic_powerdown', 'load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl', 'tx_dynamic_powerdown_cycles'], (int, bool), 0, 1), (984, 985))),
        ('load_config_defaults',
            (conf_v2._compound_property, (['enable_tx_dynamic_powerdown', 'load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl', 'tx_dynamic_powerdown_cycles'], (int, bool), 0, 1), (985, 986))),
        ('enable_fifo_diagnostics',
            (conf_v2._compound_property, (['enable_tx_dynamic_powerdown', 'load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl', 'tx_dynamic_powerdown_cycles'], (int, bool), 0, 1), (986, 987))),
        ('clk_ctrl',
            (conf_v2._compound_property, (['enable_tx_dynamic_powerdown', 'load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl', 'tx_dynamic_powerdown_cycles'], (int, bool), 0, 3), (987, 989))),
        ('tx_dynamic_powerdown_cycles',
            (conf_v2._compound_property, (['enable_tx_dynamic_powerdown', 'load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl', 'tx_dynamic_powerdown_cycles'], (int, bool), 0, 7), (989, 992))),
        ('enable_piso_upstream',
            (conf_v2._list_property, ((int,bool), 0, 1, 4, 1), (992, 996))),
        ('enable_piso_downstream',
            (conf_v2._list_property, ((int,bool), 0, 1, 4, 1), (1000, 1004))),
        ('enable_posi',
            (conf_v2._list_property, ((int,bool), 0, 1, 4, 1), (1008, 1012))),
        ('test_mode_uart0',
            (conf_v2._compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 3), (1016, 1018))),
        ('test_mode_uart1',
            (conf_v2._compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 3), (1018, 1020))),
        ('test_mode_uart2',
            (conf_v2._compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 3), (1020, 1022))),
        ('test_mode_uart3',
            (conf_v2._compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 3), (1022, 1024))),
        ('enable_cross_trigger',
            (conf_v2._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], int, 0, 1), (1024, 1025))),
        ('enable_periodic_reset',
            (conf_v2._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], int, 0, 1), (1025, 1026))),
        ('enable_rolling_periodic_reset',
            (conf_v2._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], int, 0, 1), (1026, 1027))),
        ('enable_periodic_trigger',
            (conf_v2._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], int, 0, 1), (1027, 1028))),
        ('enable_rolling_periodic_trigger',
            (conf_v2._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], int, 0, 1), (1028, 1029))),
        ('enable_periodic_trigger_veto',
            (conf_v2._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], int, 0, 1), (1029, 1030))),
        ('enable_hit_veto',
            (conf_v2._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], int, 0, 1), (1030, 1031))),
        ('shadow_reset_length',
            (conf_v2._basic_property, (int, 0, 255), (1032, 1040))),
        ('adc_burst_length',
            (conf_v2._basic_property, (int, 0, 255), (1040, 1048))),
        ('channel_mask',
            (conf_v2._list_property, (int, 0, 1, Configuration_v2.num_channels, 1), (1048, 1112))),
        ('external_trigger_mask',
            (conf_v2._list_property, (int, 0, 1, Configuration_v2.num_channels, 1), (1112, 1176))),
        ('cross_trigger_mask',
            (conf_v2._list_property, (int, 0, 1, Configuration_v2.num_channels, 1), (1176, 1240))),
        ('periodic_trigger_mask',
            (conf_v2._list_property, (int, 0, 1, Configuration_v2.num_channels, 1), (1240, 1304))),
        ('periodic_reset_cycles',
            (conf_v2._basic_property, (int, 0, 2**24-1), (1304, 1328))),
        ('periodic_trigger_cycles',
            (conf_v2._basic_property, (int, 0, 2**32-1), (1328, 1360))),
        ('enable_dynamic_reset',
            (conf_v2._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1360,1361))),
        ('enable_min_delta_adc',
            (conf_v2._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1361,1362))),
        ('threshold_polarity',
            (conf_v2._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1362,1363))),
        ('reset_length',
            (conf_v2._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int), 0, 7), (1363,1366))),
        ('mark_first_packet',
            (conf_v2._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1366,1367))),
        ('reset_threshold',
            (conf_v2._basic_property, (int, 0, 255), (1368,1376))),
        ('min_delta_adc',
            (conf_v2._basic_property, (int, 0, 255), (1376,1384))),
        ('digital_threshold',
            (conf_v2._list_property, (int, 0, 255, Configuration_v2.num_channels, 8), (1384,1896))),
        ('RESERVED',
            (conf_v2._basic_property, (int, 0, 0), (1896, 1912))),
        ('tx_slices0',
            (conf_v2._compound_property, (['tx_slices0', 'tx_slices1'], int, 0, 15), (1912, 1916))),
        ('tx_slices1',
            (conf_v2._compound_property, (['tx_slices0', 'tx_slices1'], int, 0, 15), (1916, 1920))),
        ('tx_slices2',
            (conf_v2._compound_property, (['tx_slices2', 'tx_slices3'], int, 0, 15), (1920, 1924))),
        ('tx_slices3',
            (conf_v2._compound_property, (['tx_slices2', 'tx_slices3'], int, 0, 15), (1924, 1928))),
        ('i_tx_diff0',
            (conf_v2._compound_property, (['i_tx_diff0', 'i_tx_diff1'], int, 0, 15), (1928, 1932))),
        ('i_tx_diff1',
            (conf_v2._compound_property, (['i_tx_diff0', 'i_tx_diff1'], int, 0, 15), (1932, 1936))),
        ('i_tx_diff2',
            (conf_v2._compound_property, (['i_tx_diff2', 'i_tx_diff3'], int, 0, 15), (1936, 1940))),
        ('i_tx_diff3',
            (conf_v2._compound_property, (['i_tx_diff2', 'i_tx_diff3'], int, 0, 15), (1940, 1944))),
        ('i_rx0',
            (conf_v2._compound_property, (['i_rx0', 'i_rx1'], int, 0, 15), (1944, 1948))),
        ('i_rx1',
            (conf_v2._compound_property, (['i_rx0', 'i_rx1'], int, 0, 15), (1948, 1952))),
        ('i_rx2',
            (conf_v2._compound_property, (['i_rx2', 'i_rx3'], int, 0, 15), (1952, 1956))),
        ('i_rx3',
            (conf_v2._compound_property, (['i_rx2', 'i_rx3'], int, 0, 15), (1956, 1960))),
        ('i_rx_clk',
            (conf_v2._compound_property, (['i_rx_clk', 'i_rx_rst'], int, 0, 15), (1960, 1964))),
        ('i_rx_rst',
            (conf_v2._compound_property, (['i_rx_clk', 'i_rx_rst'], int, 0, 15), (1964, 1968))),
        ('i_rx_ext_trig',
            (conf_v2._basic_property, (int, 0, 15), (1968, 1972))),
        ('r_term0',
            (conf_v2._basic_property, (int, 0, 31), (1976, 1981))),
        ('r_term1',
            (conf_v2._basic_property, (int, 0, 31), (1984, 1989))),
        ('r_term2',
            (conf_v2._basic_property, (int, 0, 31), (1992, 1997))),
        ('r_term3',
            (conf_v2._basic_property, (int, 0, 31), (2000, 2005))),
        ('r_term_clk',
            (conf_v2._basic_property, (int, 0, 31), (2008, 2013))),
        ('r_term_reset',
            (conf_v2._basic_property, (int, 0, 31), (2016, 2021))),
        ('r_term_ext_trig',
            (conf_v2._basic_property, (int, 0, 31), (2024, 2029))),
        ('v_cm_lvds_tx0',
            (conf_v2._compound_property, (['v_cm_lvds_tx0', 'v_cm_lvds_tx0'], int, 0, 7), (2032, 2035))),
        ('v_cm_lvds_tx1',
            (conf_v2._compound_property, (['v_cm_lvds_tx0', 'v_cm_lvds_tx0'], int, 0, 7), (2036, 2039))),
         ('v_cm_lvds_tx2',
            (conf_v2._compound_property, (['v_cm_lvds_tx2', 'v_cm_lvds_tx3'], int, 0, 7), (2040, 2043))),
        ('v_cm_lvds_tx3',
            (conf_v2._compound_property, (['v_cm_lvds_tx2', 'v_cm_lvds_tx3'], int, 0, 7), (2044, 2047))),

    ])

# GENERATE THE PROPERTIES!
Configuration_v2b.bit_map = OrderedDict()
Configuration_v2b.register_map = OrderedDict()
Configuration_v2b.register_names = []
conf_v2._generate_properties(Configuration_v2b, _property_configuration, verbose=True)
