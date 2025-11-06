from bitarray import bitarray
import os
import errno
import functools
from collections import OrderedDict

from .. import bitarrayhelper as bah
from .. import configs
from . import BaseConfiguration_v2, _Smart_List
from . import configuration_v2_base as v2_base

class Configuration_v3(BaseConfiguration_v2):
    '''
    Represents the desired configuration state of a LArPix v3 chip.

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
    asic_version = 3
    default_configuration_file = 'chip/default_v3.json'
    num_registers = 255
    num_bits = num_registers*8
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
            (v2_base._list_property, (int, 0, 31, Configuration_v3.num_channels, 8), (0,512))),
        ('threshold_global',
            (v2_base._basic_property, (int, 0, 255), (512, 520))),
        ('csa_bypass_enable',
            (v2_base._compound_property, (['csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (521,522))),
        ('bypass_caps_en',
            (v2_base._compound_property, (['csa_bypass_enable','bypass_caps_en'], (int,bool), 0, 1), (522,523))),
        ('csa_enable',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v3.num_channels, 1), (528, 592))),
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
            (v2_base._compound_property, (['ref_current_trim', 'adc_comp_trim'], (int, bool), 0, 31), (648, 653))),
        ('adc_comp_trim',
            (v2_base._compound_property, (['ref_current_trim', 'adc_comp_trim'], (int, bool), 0, 3), (653, 655))),
        ('vref_dac',
            (v2_base._basic_property, (int, 0, 255), (656, 664))),
        ('adc_ibias_delay',
            (v2_base._basic_property, (int, 0, 15), (664,668))),
        ('adc_ibias_delay_monitor',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (668,672))),
        ('csa_bypass_select',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v3.num_channels, 1), (672,736))),
        ('csa_monitor_select',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v3.num_channels, 1), (736,800))),
        ('csa_testpulse_enable',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v3.num_channels, 1), (800,864))),
        ('csa_testpulse_dac',
            (v2_base._basic_property, (int, 0, 255), (864,872))),
        ('current_monitor_bank0',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (872,876))),
        ('current_monitor_bank1',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (876,880))),
        ('current_monitor_bank2',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (880,884))),
        ('current_monitor_bank3',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (884,888))),
        ('voltage_monitor_bank0',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (888,892))),
        ('voltage_monitor_bank1',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (892,896))),
        ('voltage_monitor_bank2',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (896,900))),
        ('voltage_monitor_bank3',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (900,904))),         
        ('voltage_monitor_refgen',
            (v2_base._list_property, ((int,bool), 0, 1, 8, 1), (904,912))),
        ('digital_monitor_enable',
            (v2_base._compound_property, (['digital_monitor_enable','digital_monitor_select'], (bool, int), 0, 1), (912,913))),
        ('digital_monitor_select',
            (v2_base._compound_property, (['digital_monitor_enable','digital_monitor_select'], (bool, int), 0, 10), (913,916))),
        ('digital_monitor_chan',
            (v2_base._basic_property, (int, 0, 63), (920,926))),
        ('fifo_high_water_lsbs',
            (v2_base._basic_property, (int, 0, 63), (928,936))),
        ('fifo_high_water_msbs',
            (v2_base._basic_property, (int, 0, 63), (936,944))),
        ('total_packets_lsbs',
            (v2_base._basic_property, (int, 0, 63), (944,952))),
        ('total_packets_msbs',
            (v2_base._basic_property, (int, 0, 63), (952,960))),
        ('dropped_packets',
            (v2_base._basic_property, (int, 0, 63), (960,968))),
        ('adc_hold_delay',
            (v2_base._basic_property, (int, 0, 255), (968,976))),
        ('chip_id',
            (v2_base._basic_property, (int, 0, 255), (976,984))),
        ('cds_mode',
            (v2_base._compound_property, (['cds_mode', 'load_config_defaults', 'enable_fifo_diagnostics', 'enable_local_fifo_diagnostics', 'enable_tally', 'enable_external_trigger', 'enable_external_sync', 'enable_data_stats'], (int, bool), 0, 1), (984,985))),
        ('load_config_defaults',
            (v2_base._compound_property, (['cds_mode', 'load_config_defaults', 'enable_fifo_diagnostics', 'enable_local_fifo_diagnostics', 'enable_tally', 'enable_external_trigger', 'enable_external_sync', 'enable_data_stats'], (int, bool), 0, 1), (985,986))),
        ('enable_fifo_diagnostics',
            (v2_base._compound_property, (['cds_mode', 'load_config_defaults', 'enable_fifo_diagnostics', 'enable_local_fifo_diagnostics', 'enable_tally', 'enable_external_trigger', 'enable_external_sync', 'enable_data_stats'], (int, bool), 0, 1), (986,987))),
        ('enable_local_fifo_diagnostics',
            (v2_base._compound_property, (['cds_mode', 'load_config_defaults', 'enable_fifo_diagnostics', 'enable_local_fifo_diagnostics', 'enable_tally', 'enable_external_trigger', 'enable_external_sync', 'enable_data_stats'], (int, bool), 0, 1), (987,988))),
        ('enable_tally',
            (v2_base._compound_property, (['cds_mode', 'load_config_defaults', 'enable_fifo_diagnostics', 'enable_local_fifo_diagnostics', 'enable_tally', 'enable_external_trigger', 'enable_external_sync', 'enable_data_stats'], (int, bool), 0, 1), (988,989))),
        ('enable_external_trigger',
            (v2_base._compound_property, (['cds_mode', 'load_config_defaults', 'enable_fifo_diagnostics', 'enable_local_fifo_diagnostics', 'enable_tally', 'enable_external_trigger', 'enable_external_sync', 'enable_data_stats'], (int, bool), 0, 1), (989,990))),
        ('enable_external_sync',
            (v2_base._compound_property, (['cds_mode', 'load_config_defaults', 'enable_fifo_diagnostics', 'enable_local_fifo_diagnostics', 'enable_tally', 'enable_external_trigger', 'enable_external_sync', 'enable_data_stats'], (int, bool), 0, 1), (990,991))),        
        ('enable_data_stats',
            (v2_base._compound_property, (['cds_mode', 'load_config_defaults', 'enable_fifo_diagnostics', 'enable_local_fifo_diagnostics', 'enable_tally', 'enable_external_trigger', 'enable_external_sync', 'enable_data_stats'], (int, bool), 0, 1), (991,992))),
        ('enable_piso_upstream',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (992, 996))),
        ('enable_piso_downstream',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (1000, 1004))),
        ('enable_posi',
            (v2_base._list_property, ((int,bool), 0, 1, 4, 1), (1008, 1012))),
        ('en_analog_monitor',
            (v2_base._compound_property, (['en_analog_monitor','reset_threshold_msbs'], (bool, int), 0, 1), (1016,1017))),
        ('reset_threshold_msbs',
            (v2_base._compound_property, (['en_analog_monitor','reset_threshold_msbs'], (bool, int), 0, 3), (1017,1019))),
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
        ('shadow_reset_length',
            (v2_base._basic_property, (int, 0, 255), (1032,1040))),
        ('adc_burst_length',
            (v2_base._basic_property, (int, 0, 255), (1040,1048))),
        ('channel_mask',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v3.num_channels, 1), (1048,1112))),
        ('external_trigger_mask',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v3.num_channels, 1), (1112,1176))),
        ('cross_trigger_mask',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v3.num_channels, 1), (1176,1240))),
        ('periodic_trigger_mask',
            (v2_base._list_property, ((int,bool), 0, 1, Configuration_v3.num_channels, 1), (1240,1304))),
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
        ('reset_threshold_lsbs',
            (v2_base._basic_property, (int, 0, 255), (1368,1376))),
        ('min_delta_adc',
            (v2_base._basic_property, (int, 0, 255), (1376,1384))),
        ('digital_threshold',
            (v2_base._list_property, (int, 0, 255, Configuration_v3.num_channels, 8), (1384,1896))),
        ('RESERVED',
            (v2_base._basic_property, (int, 0, 255), (1896,1912))),
        ('tx_slices0',
            (v2_base._compound_property, (['tx_slices0', 'tx_slices1'], int, 0, 15), (1912, 1916))),
        ('tx_slices1',
            (v2_base._compound_property, (['tx_slices0', 'tx_slices1'], int, 0, 15), (1916, 1920))),
        ('tx_slices2',
            (v2_base._compound_property, (['tx_slices2', 'tx_slices3'], int, 0, 15), (1920, 1924))),
        ('tx_slices3',
            (v2_base._compound_property, (['tx_slices2', 'tx_slices3'], int, 0, 15), (1924, 1928))),
        ('i_tx_diff0',
            (v2_base._compound_property, (['i_tx_diff0', 'i_tx_diff1'], int, 0, 15), (1928, 1932))),
        ('i_tx_diff1',
            (v2_base._compound_property, (['i_tx_diff0', 'i_tx_diff1'], int, 0, 15), (1932, 1936))),
        ('i_tx_diff2',
            (v2_base._compound_property, (['i_tx_diff2', 'i_tx_diff3'], int, 0, 15), (1936, 1940))),
        ('i_tx_diff3',
            (v2_base._compound_property, (['i_tx_diff2', 'i_tx_diff3'], int, 0, 15), (1940, 1944))),
        ('i_rx0',
            (v2_base._compound_property, (['i_rx0', 'i_rx1'], int, 0, 3), (1944, 1946))),
        ('i_rx1',
            (v2_base._compound_property, (['i_rx0', 'i_rx1'], int, 0, 3), (1948, 1950))),
        ('i_rx2',
            (v2_base._compound_property, (['i_rx2', 'i_rx3'], int, 0, 3), (1952, 1954))),
        ('i_rx3',
            (v2_base._compound_property, (['i_rx2', 'i_rx3'], int, 0, 3), (1956, 1958))),
        ('i_rx_clk',
            (v2_base._compound_property, (['i_rx_clk', 'i_rx_rst'], int, 0, 3), (1960, 1962))),
        ('i_rx_rst',
            (v2_base._compound_property, (['i_rx_clk', 'i_rx_rst'], int, 0, 3), (1964, 1966))),
        ('i_rx_ext_trig',
            (v2_base._basic_property, (int, 0, 3), (1974, 1976))),
        ('r_term0',
            (v2_base._basic_property, (int, 0, 7), (1976, 1979))),
        ('r_term1',
            (v2_base._basic_property, (int, 0, 7), (1984, 1987))),
        ('r_term2',
            (v2_base._basic_property, (int, 0, 7), (1992, 1995))),
        ('r_term3',
            (v2_base._basic_property, (int, 0, 7), (2000, 2003))),
        ('RESERVED2',
            (v2_base._basic_property, (int, 0, 255), (2008,2032))),
        ('v_cm_lvds_tx0',
            (v2_base._compound_property, (['v_cm_lvds_tx0', 'v_cm_lvds_tx1'], int, 0, 7), (2032, 2035))),
        ('v_cm_lvds_tx1',
            (v2_base._compound_property, (['v_cm_lvds_tx0', 'v_cm_lvds_tx1'], int, 0, 7), (2036, 2039))),
         ('v_cm_lvds_tx2',
            (v2_base._compound_property, (['v_cm_lvds_tx2', 'v_cm_lvds_tx3'], int, 0, 7), (2040, 2043))),
        ('v_cm_lvds_tx3',
            (v2_base._compound_property, (['v_cm_lvds_tx2', 'v_cm_lvds_tx3'], int, 0, 7), (2044, 2047))),
    ])

# GENERATE THE PROPERTIES!
Configuration_v3.bit_map = OrderedDict()
Configuration_v3.register_map = OrderedDict()
Configuration_v3.register_names = []


v2_base._generate_properties(Configuration_v3, _property_configuration, verbose=False)



