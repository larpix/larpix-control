#!/usr/bin/env python

import larpix

# Initialize LArPix Control system
controller = larpix.Controller()
controller.set_clock_speed(10) # MHz

# Initialize four LArPix chips, on two I/O daisy chains
chip_15 = larpix.Chip(chip_id=15, io_chain=0)
chip_85 = larpix.Chip(chip_id=85, io_chain=0)
chip_170 = larpix.Chip(chip_id=170, io_chain=1)
chip_240 = larpix.Chip(chip_id=240, io_chain=1)
chips = [chip_15, chip_85, chip_170, chip_240]

controller.set_chips(chips)

# Configure chips
for chip in chips:
    # General
    chip.disable_all_channels()
    # CSA configuration
    chip.enable_internal_bypass()
    chip.disable_analog_monitor()
    chip.set_csa_gain(1)
    # ADC configuration
    chip.set_sample_cycles(1)
    chip.set_adc_burst_length(1)
    chip.disable_csa_bypass()
    # Self-trigger configuration
    chip.set_cross_trigger_mode(0)
    # Discriminator configuration
    chip.set_reset_cycles(0xA00) # 1024 us @ 10 MHz master clock
    chip.enable_periodic_reset()
    chip.set_global_threshold(16)
    chip.set_pixel_trim_thresholds([16]*32)
    # General
    chip.disable_fifo_diagnostic()
    chip.enable_normal_operation()



############################################################################
# Regular data acquisition
for chip in chips:
    chip.enable_all_channels()

controller.run(time=60) # run for fixed time, in seconds

for chip in chips:
    chip.disable_all_channels()


############################################################################
# External trigger mode
for chip in chips:
    chip.enable_external_trigger()  #Accept optional channel map

controller.run(time=60) # run for fixed time, in seconds

for chip in chips:
    chip.disable_external_trigger()


############################################################################
# CSA Test pulse mode:
for chip in chips:
    chip.set_testpulse_dac(124)
    chip.enable_testpulse() #Accept optional channel map

controller.run_testpulse() # run long enough to collect all test pulse data

for chip in chips:
    chip.disable_testpulse()
    chip.set_testpulse_dac(0)

############################################################################
# FIFO Test mode:
for chip in chips:
    chip.enable_fifo_diagnostic()
    chip.set_fifo_test_burst_length(0x00FF)
    chip.enable_fifo_test_mode()

controller.run_fifo_test()

for chip in chips:
    chip.disable_fifo_test_mode()
    chip.disable_fifo_diagnostic()


############################################################################
# CSA Analog Monitor mode:
for chan_num in range(32):
    for chip in chips:
        chip.enable_external_trigger(channel_number = chan_num)
        chip.enable_analog_monitor(channel_number = chan_num)
    controller.run_analog_monitor_test()
for chip in chips:
    chip.disable_analog_monitor()
    chip.disable_external_trigger()
