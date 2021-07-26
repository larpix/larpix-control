from bitarray import bitarray
import os
import errno
import functools
from collections import OrderedDict

from .. import bitarrayhelper as bah
from .. import configs
from . import BaseConfiguration_v2, _Smart_List
from . import configuration_v2_base as v2_base

class Configuration_v2(BaseConfiguration_v2):
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

    def __init__(self):
        # Note: properties, getters and setters are constructed after this class definition at the bottom of the file.
        super(BaseConfiguration_v2, self).__init__()
        return

## Set up property info
#
_property_configuration = OrderedDict([
        ('pixel_trim_dac',
            (v2_base._list_property, (int, 0, 31, Configuration_v2.num_channels, 8), (0,512))),
        ('threshold_global',
            (v2_base._basic_property, (int, 0, 255), (512, 520))),
        ('csa_gain',
            (v2_base._compound_property, (['csa_gain', 'csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (520,521))),
        ('csa_bypass_enable',
            (v2_base._compound_property, (['csa_gain', 'csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (521,522))),
        ('bypass_caps_en',
            (v2_base._compound_property, (['csa_gain', 'csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (522,523))),
        ('csa_enable',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (528, 592))),
        ('ibias_tdac',
            (v2_base._basic_property, (int, 0, 15), (592, 596))),
        ('ibias_comp',
            (v2_base._basic_property, (int, 0, 15), (600, 604))),
        ('ibias_buffer',
            (v2_base._basic_property, (int, 0, 15), (608, 612))),
        ('ibias_csa',
            (v2_base._basic_property, (int, 0, 15), (616, 620))),
        ('ibias_vref_buffer',
            (v2_base._basic_property, (int, 0, 15), (624, 628))),
        ('ibias_vcm_buffer',
            (v2_base._basic_property, (int, 0, 15), (632, 636))),
        ('ibias_tpulse',
            (v2_base._basic_property, (int, 0, 15), (640, 644))),
        ('ref_current_trim',
            (v2_base._compound_property, (['ref_current_trim','override_ref','ref_kickstart'], int, 0, 31), (648, 653))),
        ('override_ref',
            (v2_base._compound_property, (['ref_current_trim','override_ref','ref_kickstart'], (int,bool), 0, 1), (653, 654))),
        ('ref_kickstart',
            (v2_base._compound_property, (['ref_current_trim','override_ref','ref_kickstart'], (int,bool), 0, 1), (654, 655))),
        ('vref_dac',
            (v2_base._basic_property, (int, 0, 255), (656, 664))),
        ('vcm_dac',
            (v2_base._basic_property, (int, 0, 255), (664,672))),
        ('csa_bypass_select',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (672,736))),
        ('csa_monitor_select',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (736,800))),
        ('csa_testpulse_enable',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (800,864))),
        ('csa_testpulse_dac',
            (v2_base._basic_property, (int, 0, 255), (864,872))),
        ('current_monitor_bank0',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (872,876))),
        ('current_monitor_bank1',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (880,884))),
        ('current_monitor_bank2',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (888,892))),
        ('current_monitor_bank3',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (896,900))),
        ('voltage_monitor_bank0',
            (v2_base._list_property, ((int,bool), 0, 1, 3, 1), (904,907))),
        ('voltage_monitor_bank1',
            (v2_base._list_property, ((int,bool), 0, 1, 3, 1), (912,915))),
        ('voltage_monitor_bank2',
            (v2_base._list_property, ((int,bool), 0, 1, 3, 1), (920,923))),
        ('voltage_monitor_bank3',
            (v2_base._list_property, ((int,bool), 0, 1, 3, 1), (928,931))),
        ('voltage_monitor_refgen',
            (v2_base._list_property, ((int,bool), 0, 1, 8, 1), (936,944))),
        ('digital_monitor_enable',
            (v2_base._compound_property, (['digital_monitor_enable','digital_monitor_select'], (int,bool), 0, 1), (944,945))),
        ('digital_monitor_select',
            (v2_base._compound_property, (['digital_monitor_enable','digital_monitor_select'], (int,bool), 0, 10), (945,949))),
        ('digital_monitor_chan',
            (v2_base._basic_property, (int, 0, 63), (952,958))),
        ('slope_control0',
            (v2_base._compound_property, (['slope_control0', 'slope_control1'], int, 0, 15), (960,964))),
        ('slope_control1',
            (v2_base._compound_property, (['slope_control0', 'slope_control1'], int, 0, 15), (964,968))),
        ('slope_control2',
            (v2_base._compound_property, (['slope_control2', 'slope_control3'], int, 0, 15), (968,972))),
        ('slope_control3',
            (v2_base._compound_property, (['slope_control2', 'slope_control3'], int, 0, 15), (972,976))),
        ('chip_id',
            (v2_base._basic_property, (int, 0, 255), (976,984))),
        ('load_config_defaults',
            (v2_base._compound_property, (['load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl'], (int,bool), 0, 1), (985,986))),
        ('enable_fifo_diagnostics',
            (v2_base._compound_property, (['load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl'], (int,bool), 0, 1), (986,987))),
        ('clk_ctrl',
            (v2_base._compound_property, (['load_config_defaults', 'enable_fifo_diagnostics', 'clk_ctrl'], (int), 0, 2), (987,989))),
        ('enable_miso_upstream',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (992,996))),
        ('enable_miso_downstream',
            (v2_base._compound_list_property, (['enable_miso_downstream', 'enable_miso_differential'], (int,bool), 0, 1, 4, 1), (1000,1004))),
        ('enable_miso_differential',
            (v2_base._compound_list_property, (['enable_miso_downstream', 'enable_miso_differential'], (int,bool), 0, 1, 4, 1), (1004,1008))),
        ('enable_mosi',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (1008,1012))),
        ('test_mode_uart0',
            (v2_base._compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 4), (1016,1018))),
        ('test_mode_uart1',
            (v2_base._compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 4), (1018,1020))),
        ('test_mode_uart2',
            (v2_base._compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 4), (1020,1022))),
        ('test_mode_uart3',
            (v2_base._compound_property, (['test_mode_uart0', 'test_mode_uart1', 'test_mode_uart2', 'test_mode_uart3'], int, 0, 4), (1022,1024))),
        ('enable_cross_trigger',
            (v2_base._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1024,1025))),
        ('enable_periodic_reset',
            (v2_base._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1025,1026))),
        ('enable_rolling_periodic_reset',
            (v2_base._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1026,1027))),
        ('enable_periodic_trigger',
            (v2_base._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1027,1028))),
        ('enable_rolling_periodic_trigger',
            (v2_base._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1028,1029))),
        ('enable_periodic_trigger_veto',
            (v2_base._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1029,1030))),
        ('enable_hit_veto',
            (v2_base._compound_property, (['enable_cross_trigger', 'enable_periodic_reset', 'enable_rolling_periodic_reset', 'enable_periodic_trigger', 'enable_rolling_periodic_trigger', 'enable_periodic_trigger_veto', 'enable_hit_veto'], (int,bool), 0, 1), (1030,1031))),
        ('adc_hold_delay',
            (v2_base._basic_property, (int, 0, 15), (1032,1036))),
        ('adc_burst_length',
            (v2_base._basic_property, (int, 0, 255), (1040,1048))),
        ('channel_mask',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (1048,1112))),
        ('external_trigger_mask',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (1112,1176))),
        ('cross_trigger_mask',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (1176,1240))),
        ('periodic_trigger_mask',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v2.num_channels, 1), (1240,1304))),
        ('periodic_reset_cycles',
            (v2_base._basic_property, (int, 0, 2**24-1), (1304,1328))),
        ('periodic_trigger_cycles',
            (v2_base._basic_property, (int, 0, 2**32-1), (1328,1360))),
        ('enable_dynamic_reset',
            (v2_base._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1360,1361))),
        ('enable_min_delta_adc',
            (v2_base._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1361,1362))),
        ('threshold_polarity',
            (v2_base._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1362,1363))),
        ('reset_length',
            (v2_base._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int), 0, 7), (1363,1366))),
        ('mark_first_packet',
            (v2_base._compound_property, (['enable_dynamic_reset', 'enable_min_delta_adc', 'threshold_polarity', 'reset_length', 'mark_first_packet'], (int,bool), 0, 1), (1366,1367))),
        ('reset_threshold',
            (v2_base._basic_property, (int, 0, 255), (1368,1376))),
        ('min_delta_adc',
            (v2_base._basic_property, (int, 0, 255), (1376,1384))),
        ('digital_threshold',
            (v2_base._list_property, (int, 0, 255, Configuration_v2.num_channels, 8), (1384,1896))),
    ])

# GENERATE THE PROPERTIES!
Configuration_v2.bit_map = OrderedDict()
Configuration_v2.register_map = OrderedDict()
Configuration_v2.register_names = []


v2_base._generate_properties(Configuration_v2, _property_configuration, verbose=False)



