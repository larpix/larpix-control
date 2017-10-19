#!/usr/bin/env python

import larpix

# Initialize LArPix Control system
controller = larpix.Controller()

## This line is no longer possible because the FPGA firmware controls
## the clock speed.
# controller.set_clock_speed(10) # MHz

# Initialize four LArPix chips, on two I/O daisy chains
chip_15 = larpix.Chip(chip_id=15, io_chain=0)
chip_85 = larpix.Chip(chip_id=85, io_chain=0)
chip_170 = larpix.Chip(chip_id=170, io_chain=1)
chip_240 = larpix.Chip(chip_id=240, io_chain=1)
chips = [chip_15, chip_85, chip_170, chip_240]

controller.chips = chips

# Configure chips
for chip in chips:
    # General
    chip.config.disable_channels()
    # CSA configuration
    chip.config.internal_bypass = 1
    chip.config.disable_analog_monitor()
    chip.config.csa_gain = 1
    # ADC configuration
    chip.config.sample_cycles = 1
    chip.config.adc_burst_length = 1
    chip.config.csa_bypass = 0
    # Self-trigger configuration
    chip.config.cross_trigger_mode = 0
    # Discriminator configuration
    chip.config.reset_cycles = 0xA00 # 1024 us @ 10 MHz master clock
    chip.config.periodic_reset = 1
    chip.config.global_threshold = 16
    chip.config.pixel_trim_thresholds = [16]*32
    # General
    chip.config.fifo_diagnostic = 0
    chip.config.enable_normal_operation()



############################################################################
# Regular data acquisition
for chip in chips:
    chip.config.enable_channels()

controller.run(timelimit=1) # run for fixed time, in seconds
print('ran normal operation for 1 second')

for chip in chips:
    chip.config.disable_channels()


############################################################################
# External trigger mode
for chip in chips:
    chip.config.enable_external_trigger()  #Accept optional channel map

controller.run(timelimit=1) # run for fixed time, in seconds
print('ran in external trigger mode for 1 second')

for chip in chips:
    chip.config.disable_external_trigger()


############################################################################
# CSA Test pulse mode:
for chip in chips:
    chip.config.csa_testpulse_dac_amplitude = 124
    chip.config.enable_testpulse() #Accept optional channel map

controller.run_testpulse(range(32)) # run long enough to collect all test pulse data

for chip in chips:
    chip.config.disable_testpulse()
    chip.config.testpulse_dac = 0

############################################################################
# FIFO Test mode:
for chip in chips:
    chip.config.fifo_diagnostic = 1
    chip.config.fifo_test_burst_length = 0x00FF
    chip.config.test_mode = larpix.Configuration.TEST_FIFO

controller.run_fifo_test()

for chip in chips:
    chip.config.test_mode = larpix.Configuration.TEST_OFF
    chip.config.fifo_diagnostic = 0


############################################################################
# CSA Analog Monitor mode:
for chan_num in range(32):
    for chip in chips:
        chip.config.enable_external_trigger([chan_num])
        chip.config.enable_analog_monitor(chan_num)
    controller.run_analog_monitor_test()
for chip in chips:
    chip.config.disable_analog_monitor()
    chip.config.disable_external_trigger()
