'''
Quickstart commands for test boards
'''

from __future__ import absolute_import
from __future__ import print_function
import sys

import larpix.larpix as larpix
from larpix.io.zmq_io import ZMQ_IO
from larpix.logger.h5_logger import HDF5Logger

## For interactive mode
VERSION = sys.version_info
if VERSION[0] < 3:
    input = raw_input
##

def silence_chips(controller, interactive):
    '''Silence all chips in controller'''
    for chip_key in controller.chips:
        chip = controller.get_chip(chip_key)
        if interactive:
            print('Silencing chip %d' % chip.chip_id)
        chip.config.global_threshold = 255
        controller.write_configuration(chip_key,32)
        if interactive:
            input('Just silenced chip %d. <enter> when ready.\n' % chip.chip_id)
    return

def set_config_physics(controller, interactive):
    '''Set the chips for the default physics configuration'''
    for chip_key in controller.chips:
        chip = controller.get_chip(chip_key)
        if interactive:
            x = input('Configuring chip %d. <enter> to continue, q to quit' % chip.chip_id)
            if x == 'q':
                break
        chip.config.internal_bypass = 1
        controller.write_configuration(chip_key,33)
        chip.config.periodic_reset = 1
        controller.write_configuration(chip_key,47)
        chip.config.global_threshold = 60
        controller.write_configuration(chip_key,32)
        chip.config.reset_cycles = 4096
        controller.write_configuration(chip_key,range(60,63))
        print('configured {}'.format(str(chip)))
    return

def quickcontroller(board='pcb-5', interactive=False, io=None, logger=None,
    log_filepath=None):
    '''Quick jump through all controller creation and config steps'''
    controller_config = 'controller/{}_chip_info.json'.format(board)
    if io is None:
        io_config = 'io/daq-srv1.json'
        io = ZMQ_IO(io_config)
    if logger is None:
        logger = HDF5Logger(filename=log_filepath)
        logger.open()
    controller = larpix.Controller()
    controller.io = io
    controller.logger = logger
    controller.load(controller_config)
    silence_chips(controller, interactive)
    set_config_physics(controller, interactive)
    return controller

# Short-cut handle
qc = quickcontroller

