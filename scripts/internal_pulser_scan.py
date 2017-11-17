'''
This script drives the internal pulser on the specified chip + channel.

'''
from __future__ import absolute_import

import logging
import larpix.larpix as larpix

from larpix.tasks import startup, get_chip_ids

# Add a useful static class property
larpix.Controller.max_chip_id = 255

# Define helper functions
def broadcast_chips(controller, iochains=[0,]):
    '''If chips list is known, return.  If not, create broadcast list.'''
    chips = controller.chips[:]
    if len(chips)==0:
        # No known chips.  Broadcast to all possible chips.
        for iochain in iochains:
            chips += [larpix.Chip(i,iochain)
                      for i in range(controller.max_chip_id+1)]
    return chips

def silence_chips(controller, max_chain_length=2, iochains=[0,]):
    '''Increase channel threshold in order to silence chip output.'''
    chips = broadcast_chips(controller, iochains)
    # Set global threshold
    gt_address = larpix.Configuration.global_threshold_address
    for chip_pos in range(max_chain_length):
        # Must repeat at least once for each chip position in daisy chain
        for chip in chips:
            chip.config.global_threshold = 255
            controller.write_configuration(chip,gt_address)
    return

# Create list of responsive chips, attach to controller
def autoload_chips(controller, iochains=[0,]):
    '''Send request to all possible chips, and look for responses'''
    controller.run(0.1) # flush the serial/fpga buffer
    chips = broadcast_chips(controller, iochains)
    found_chips = []
    for chip in chips:
        # Choose arbitrary non-zero register for test
        read_address = larpix.Configuration.csa_gain_and_bypasses_address
        # Read this register
        controller.read_configuration(chip,read_address)
        controller.run(0.01)
        # FIXME: Need method to read returned packet,
        # independent of chip object!
        # if returned value is not zero, then add chip to found list
        found_chips.append( chip )
    controller.chips = found_chips
    return


def initialize_chips(controller):
    '''Set improved defaults for general chip operation'''
    # FIXME: convert to load standard json config file instead?
    for chip in controller.chips:
        # reset_cycles
        chip.config.enable_periodic_reset = 1
        # internal bypass
        chip.config.internal_bypass = 1
        # global threshold
        chip.config.global_threshold = 60
        addresses = [
            # Note: order matters!
            chip.Configuration.test_mode_xtrig_reset_diag_address,
            chip.Configuration.csa_gain_and_bypasses_address,
            chip.Configuration.global_threshold_address,
        ]
        controller.write_configuration(chip,addresses)
    return

def pulse_channel(controller, chip, dac_value):
    '''Send a single pulse to chip'''
    # Assumes internal pulse mode has already been enabled for this chip
    address = chip.Configuration.csa_testpulse_dac_amplitude_address
    chip.config.csa_testpulse_dac = dac_value
    controller.write_configuration(chip,address)
    # Pulse occurs on DAC return to zero.
    chip.config.csa_testpulse_dac = 0
    controller.write_configuration(chip,address)
    return

def scan_pulser(controller,
                select_chips=None,
                channel_enable=[0,]*32, # Active low
                dac_values=range(0,256,8)+[255,],
                n_pulses = 10,
                monitor_channel=None):
    '''Scan internal pulser with a range of DAC values'''
    # Set configuration and pulse
    for chip in controller.chips:
        if select_chips:
            # Filter based on request
            if (chip.iochain, chip.chip_id) not in select_chips:
                continue
        # Enable test pulse
        chip.config.csa_testpulse_enable = channel_enable
        controller.write(chip,
                         chip.Configuration.csa_testpulse_enable_addresses)
        # Enable analog monitor
        if monitor_channel:
            chip.config.csa_monitor_select[monitor_channel]=1
            controller.write(chip,
                             chip.Configuration.csa_monitor_select_addresses)
        # Loop over pulse amplitudes
        for dac_value in dac_values:
            # Pulse this chip n times
            for idx in range(n_pulses):
                pulse_chip(controller,chip,dac_value)
                # FIXME: Add wait time between pulses?
        # Disable test pulse
        chip.config.csa_testpulse_enable = [1,]*32 # Active low
        controller.write(chip,
                         chip.Configuration.csa_testpulse_enable_addresses)
        # Disable analog monitor
        if monitor_channel:
            chip.config.csa_monitor_select[monitor_channel]=0
            controller.write(chip,
                             chip.Configuration.csa_monitor_select_addresses)
    # Done with scan
    return


def parse_larpix_arguments():
    '''Reusable argument parser for larpix testing'''
    # Had to copy code for arg parser from tasks.py
    # Should move to method in tasks.py than can be loaded from other scripts
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('--logfile', default='tasks.log',
            help='the logfile to save')
    parser.add_argument('-p', '--port', default='/dev/ttyUSB1',
            help='the serial port')
    parser.add_argument('-l', '--list', action='store_true',
            help='list available tasks')
    parser.add_argument('-t', '--task', nargs='+', default=tasks.keys(),
            help='specify tasks(s) to run')
    parser.add_argument('--chipid', nargs='*', type=int,
            help='list of chip IDs')
    parser.add_argument('--iochain', nargs='*', type=int,
            help='list of IO chain IDs (corresponding to chipids')
    parser.add_argument('-f', '--filename', default='out.txt',
            help='filename to save data to')
    parser.add_argument('-m', '--message', default='',
            help='message to save to the logfile')
    parser.add_argument('--config', default='default.json',
            help='configuration file to load')
    parser.add_argument('--runtime', default=1, type=float,
            help='number of seconds to take data for')
    args = parser.parse_args()
    if args.list:
        print('\n'.join(tasks.keys()))
        sys.exit(0)
    if args.chipid and args.iochain:
        chipset = list(zip(args.chipid, args.iochain))
    else:
        chipset = None
    settings = {
            'port': args.port,
            'chipset': chipset,
            'logfile': args.logfile,
            'filename': args.filename,
            'config': args.config,
            'runtime': args.runtime,
            }
    return settings




if '__main__' == __name__:

    # Parse input arguments
    settings = parse_larpix_arguments()

    # Setup logger
    setup_logger(settings)
    logger = logging.getLogger(__name__)
    logger.info('-'*60)
    logger.info(args.message)

    # Create controller
    controller = larpix.Controller(settings['port'])
    controller.timeout = 0.1

    # Silence chips
    startup(settings)
    # Scan and autoload chips
    controller.chips = tasks.get_chip_ids(settings)
    # Initialize to 'improved' default configuration
    for chip in controller.chips:
        chip.config.load('physics.json')
        controller.write_configuration(chip)


    ##########################################################################
    # Everything to this point should be a standard procedure before any test.
    ##########################################################################

    # Specifics for internal pulser scan

    # Consider making these optional arguments
    global_chip_ids = [(0,246),] # Shorthand: (iochain, chip_id)
    channel_enable = [0,] + [1,]*31  # First channel only (Active low.)
    pulser_dac_values = range(0,256,8)+[255,]
    n_pulses_per_value = 10  # Number of pulses at each DAC value
    analog_monitor_channel = 0 # Optionally enable analog monitor by chan num

    # Scan internal pulser
    scan_pulser(controller,
                select_chips=global_chip_ids,
                channel_enable = channel_enable,
                dac_values=pulser_dac_values,
                n_pulses=n_pulses_per_value)
    #           analog_monitor_channel = analog_monitor_channel)

    # Consider promoting to class methods:
    # controller.silence_chips()
    # controller.autoload_chips()
    # controller.initialize_chips()
    # controller.scan_pulser()
