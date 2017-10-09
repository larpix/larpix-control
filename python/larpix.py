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

    def set_pixel_trim_thresholds(self, thresholds):
        pass

    def set_global_threshold(self, threshold):
        pass

    def set_csa_gain(self, gain):
        pass

    def enable_

class Configuration(object):
    '''
    Represents the desired configuration state of a LArPix chip.

    '''
    def __init__(self):
        self._pixel_trim_thresholds = [0] * larpix.larpix_num_channels()
        self._global_threshold = 0
        self._csa_gain = 0
        self._csa_bypass = 0
        self._internal_bypass = 0
        self._csa_bypass_select = [0] * larpix.larpix_num_channels()
        self._csa_monitor_select = [0] * larpix.larpix_num_channels()
        self._csa_testpulse_enable = [0] * larpix.larpix_num_channels()
        self._csa_testpulse_dac_amplitude = [0] * larpix.larpix_num_channels()
        self._test_mode = 0
        self._cross_trigger_mode = 0
        self._periodic_reset = 0
        self._fifo_diagnostic = 0
        self._sample_cycles = 0
        self._test_burst_length = 0
        self._adc_burst_length = 0
        self._channel_mask = 0
        self._external_trigger_mask = 0
        self._reset_cycles = 0
        
        self._configuration = self.get_ctypes_configuration() 

    def get_ctypes_configuration(self):
        return_config = l.larpix_configuration()

        for i,value in enumerate(self._pixel_trim_thresholds):
            return_config.pixel_trim_thresholds[i] = value
        return_config.global_threshold = self._global_threshold
        return_config.csa_gain = self._csa_gain
        return_config.csa_bypass = self._csa_bypass
        return_config.internal_bypass = self._internal_bypass
        for i,value in enumerate(self._csa_bypass_select):
            return_config.csa_bypass_select[i] = value
        for i,value in enumerate(self._csa_monitor_select):
            return_config.csa_monitor_select[i] = value
        for i,value in enumerate(self._csa_testpulse_enable):
            return_config.csa_testpulse_enable[i] = value
        return_config.csa_testpulse_dac_amplitude = self._csa_testpulse_dac_amplitude
        return_config.test_mode = self._test_mode
        return_config.cross_trigger_mode = self._cross_trigger_mode
        return_config.periodic_reset = self._periodic_reset
        return_config.fifo_diagnostic = self._fifo_diagnostic
        return_config.sample_cycles = self._sample_cycles
        for i,value in enumerate(self._test_burst_length):
            return_config.test_burst_length[i] = value
        return_config.adc_burst_length = self._adc_burst_length
        for i,value in enumerate(self._channel_mask):
            return_config.channel_mask[i] = value
        for i,value in enumerate(self._external_trigger_mask):
            return_config.external_trigger_mask[i] = value
        for i,value in enumerate(self._reset_cycles):
            return_config.reset_cycles[i] = value
        
        return return_config

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

