'''
A module to control the LArPix chip.

'''

import larpix_c as l
import ctypes as c

class Chip(object):
    '''
    Represents one LArPix chip and helps with configuration and packet
    generation.

    '''
    def __init__(self, chip_id, io_chain):
        self.chip_id = chip_id
        self.io_chain = io_chain
        self.data_to_send = []
        
        self.configuration = Configuration()

    def set_pixel_trim_thresholds(self, thresholds):
        if len(thresholds) != l.larpix_num_channels():
            return 1
        for i,value in enumerate(thresholds):
            self.configuration.pixel_trim_thresholds[i] = value
        return 0

    def set_global_threshold(self, threshold):
        self.configuration.global_threshold = threshold
        return 0

    def set_csa_gain(self, gain):
        self.configuration.csa_gain = gain
        return 0

    def enable_channels(self, map):
        self.configuration.channel_mask = self.configuration.channel_mask & ~map 
        return 0

    def disable_channels(self, map):
        self.configuration.channel_mask = self.configuration.channel_mask | map
        return 0

    def enable_all_channels(self):
        return self.enable_channels(0xFFFFFFFF)

    def disable_all_channels(self):
        return self.disable_channels(0xFFFFFFFF)

    def enable_normal_operation(self):
        return

    def enable_external_trigger(self, map):
        self.configuration.external_trigger_mask = self.external_trigger_mask & ~map
        return 0

    def disable_external_trigger(self, map):
        self.configuration.external_trigger_mask = self.external_trigger_mask | map
        return 0

    def set_testpulse_dac(self, value):
        self.configuration.csa_testpulse_dac_amplitude = value
        return 0

    def enable_testpulse(self, map):
        for i in range(l.larpix_num_channels()):
            if (map >> i) & 1 is 1:
                self.configuration.csa_testpulse_enable[i] = 1
        return 0

    def disable_testpulse(self, map):
        for i in range(l.larpix_num_channels()):
            if (map >> i) & 1 is 1:
                self.configuration.csa_testpulse_enable[i] = 0
        return 0
    
    def enable_fifo_diagnostic(self):
        self.configuration.fifo_diagnostic = 1
        return 0

    def diable_fifo_diagnostic(self):
        self.configuration.fifo_diagnostic = 0
        return 0

    def set_fifo_test_burst_length(self, value):
        self.configuration.test_burst_length = value
        return 0

    def enable_fifo_test_mode(self):
        self.configuration.test_mode = 0x10
        return 0

    def disable_fifo_test_mode(self):
        self.configuration.test_mode = 0x0;
        return 0

    def enable_analog_monitor(self, map):
        for i in range(l.larpix_num_channels()):
            if (map >> i) & 1 is 1:
                self.configuration.csa_monitor_select[i] = 0
        return 0

    def disable_analog_monitor(self, map):
        for i in range(l.larpix_num_channels()):
            if (map >> i) & 1 is 1:
                self.configuration.csa_monitor_select[i] = 1
        return

class Configuration(object):
    '''
    Represents the desired configuration state of a LArPix chip.

    '''
    def __init__(self):
        self.pixel_trim_thresholds = [0x10] * larpix.larpix_num_channels()
        self.global_threshold = 0x10
        self.csa_gain = 1
        self.csa_bypass = 0
        self.internal_bypass = 1
        self.csa_bypass_select = [0] * larpix.larpix_num_channels()
        self.csa_monitor_select = [1] * larpix.larpix_num_channels()
        self.csa_testpulse_enable = [0] * larpix.larpix_num_channels()
        self.csa_testpulse_dac_amplitude = 0
        self.test_mode = 0
        self.cross_trigger_mode = 0
        self.periodic_reset = 0
        self.fifo_diagnostic = 0
        self.sample_cycles = 1
        self.test_burst_length = 0x00FF
        self.adc_burst_length = 0
        self.channel_mask = 0
        self.external_trigger_mask = 0xFFFFFFF
        self.reset_cycles = 0x001000
        
    def get_ctypes_configuration(self):
        ctypes_config = l.larpix_configuration()

        for i,value in enumerate(self._pixel_trim_thresholds):
            ctypes_config.pixel_trim_thresholds[i] = value
        ctypes_config.global_threshold = self._global_threshold
        ctypes_config.csa_gain = self._csa_gain
        ctypes_config.csa_bypass = self._csa_bypass
        ctypes_config.internal_bypass = self._internal_bypass
        for i,value in enumerate(self._csa_bypass_select):
            ctypes_config.csa_bypass_select[i] = value
        for i,value in enumerate(self._csa_monitor_select):
            ctypes_config.csa_monitor_select[i] = value
        for i,value in enumerate(self._csa_testpulse_enable):
            ctypes_config.csa_testpulse_enable[i] = value
        ctypes_config.csa_testpulse_dac_amplitude = self._csa_testpulse_dac_amplitude
        ctypes_config.test_mode = self._test_mode
        ctypes_config.cross_trigger_mode = self._cross_trigger_mode
        ctypes_config.periodic_reset = self._periodic_reset
        ctypes_config.fifo_diagnostic = self._fifo_diagnostic
        ctypes_config.sample_cycles = self._sample_cycles
        for i,value in enumerate(self._test_burst_length):
            ctypes_config.test_burst_length[i] = value
        ctypes_config.adc_burst_length = self._adc_burst_length
        for i,value in enumerate(self._channel_mask):
            ctypes_config.channel_mask[i] = value
        for i,value in enumerate(self._external_trigger_mask):
            ctypes_config.external_trigger_mask[i] = value
        for i,value in enumerate(self._reset_cycles):
            ctypes_config.reset_cycles[i] = value
        
        return ctypes_config

    def get_uarts(self):
        pass

class Controller(object):
    '''
    Controls a collection of LArPix Chip objects.

    '''
    def __init__(self):
        self.chips = []
        self.connection = l.larpix_connection()

    def set_chips(self, chips):
        self.chips = chips

    def set_clock_speed(self, speed_MHz):
        # TODO figure out the math here
        self.connection.clk_divisor = speed_MHz

    def write_configuration(self):
        return

    def run(self, time):
        return

    def run_testpulse(self, map):
        return

    def run_fifo_test(self):
        return

    def run_analog_monitor_teest(self):
        return
