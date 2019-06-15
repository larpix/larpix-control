'''
Quickstart commands for test boards
'''

from __future__ import absolute_import
from __future__ import print_function
import sys

import larpix.larpix as larpix
from larpix.io.serialport import SerialPort, enable_logger
from larpix.io.zmq_io import ZMQ_IO
from larpix.logger.h5_logger import HDF5Logger

## For interactive mode
VERSION = sys.version_info
if VERSION[0] < 3:
    input = raw_input
##


#List of LArPix test board configurations
board_info_list = [
    {'name':'unknown',
     'file':None,
     'chip_list':[('0-{}'.format(chip_id), chip_id) for chip_id in range(0,256)],},
    {'name':'pcb-6',
     'file':'controller/pcb-6_chip_info.json'},
    {'name':'pcb-5',
     'file':'controller/pcb-5_chip_info.json'},
    {'name':'pcb-4',
     'file':'controller/pcb-4_chip_info.json'},
    {'name':'pcb-1',
     'file':'controller/pcb-1_chip_info.json'},
    {'name':'pcb-2',
     'file':'controller/pcb-2_chip_info.json'},
    {'name':'pcb-3',
     'file':'controller/pcb-3_chip_info.json'},
    {'name':'pcb-10',
     'file':'controller/pcb-10_chip_info.json'}
]

#Create handy map by board name
board_info_map = dict([(elem['name'],elem) for elem in board_info_list])

def create_controller(timeout=0.01, io=None):
    '''Create a default controller'''
    c = larpix.Controller()
    c.io = io
    return c

def init_controller(controller, board='pcb-2'):
    '''Initialize controller'''
    if not board in board_info_map.keys():
        board = 'unknown'
    board_info = board_info_map[board]
    if board_info['file']:
        controller.load(board_info['file'])
    else:
        for chip_info in board_info['chip_list']:
            key = (chip_info[1], chip_info[0]) # daisy_chain_id, chip_id
            controller.chips[key] = larpix.Chip(chip_info[0], key)
    controller.board_info = board_info
    return controller

def silence_chips(controller, interactive):
    '''Silence all chips in controller'''
    #for _ in controller.chips:
    for chip_key in controller.chips:
        chip = controller.get_chip(chip_key)
        if interactive:
            print('Silencing chip %d' % chip.chip_id)
        chip.config.global_threshold = 255
        controller.write_configuration(chip_key,32)
        if interactive:
            input('Just silenced chip %d. <enter> when ready.\n' % chip.chip_id)
    return

def disable_chips(controller):
    '''Silence all chips in controller'''
    #for _ in controller.chips:
    for chip_key in controller.chips:
        chip = controller.get_chip(chip_key)
        chip.config.disable_channels()
        controller.write_configuration(chip_key,range(52,56))
    return

def set_config_physics(controller, interactive):
    '''Set the chips for the default physics configuration'''
    #import time
    for chip_key in controller.chips:
        '''if not board is None:
            try:
                chip.config.load('physics-%s-c%d.json' % (board, chip.chip_id))
            except Exception as e:
                print('failed to load chip specific config - error: %s' % e)
                chip.config.load('physics.json')
        else:
            chip.config.load('physics.json')
        controller.write_configuration(chip)'''
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
        #time.sleep(2)
        print('configured chip {}'.format(str(chip)))
    return

def flush_stale_data(controller):
    '''Read and discard buffer contents'''
    controller.run(1,'flush_buffer')
    controller.reads = []
    return

def get_chip_ids(**settings):
    '''
    Return a list of Chip objects representing the chips on the board.

    Checks if a chip is present by adjusting one channel's pixel trim
    threshold and checking to see that the correct configuration is read
    back in.
    '''
    logger = logging.getLogger(__name__)
    logger.info('Executing get_chip_ids')
    if 'controller' in settings:
        controller = settings['controller']
    else:
        controller = larpix.Controller(settings['port'])
    controller.use_all_chips = True
    stored_timeout = controller.timeout
    controller.timeout=0.1
    chips = {}
    chip_regs = [(c.chip_key, 0) for c in controller.all_chips]
    controller.multi_read_configuration(chip_regs, timeout=0.1)
    for chip_key in controller.all_chips:
        chip = controller.get_chip(chip_key)
        if len(chip.reads) == 0:
            print('Chip ID %d: No packet recieved' %
                  chip.chip_id)
            continue
        if len(chip.reads[0]) != 1:
            print('Cannot determine if chip %d exists because more'
                    'than 1 packet was received (expected 1)' %
                    chip.chip_id)
            continue
        if chip.reads[0][0].register_data != 0:
            chips.append(chip)
            logger.info('Found chip %s' % chip)
    controller.timeout = stored_timeout
    controller.use_all_chips = False
    return chips

def quickcontroller(board='pcb-1', interactive=False, io=None, logger=None,
    log_filepath=None):
    '''Quick jump through all controller creation and config steps'''
    if io is None:
        io = ZMQ_IO('tcp://10.0.1.6')
        # io = SerialPort(baudrate=1000000,
            # timeout=0.01)
    enable_logger()
    cont = create_controller(io=io)
    if logger is None:
        cont.logger = HDF5Logger(filename=log_filepath)
    cont.logger.open()
    init_controller(cont,board)
    silence_chips(cont, interactive)
    if cont.board_info['name'] == 'unknown':
        # Find and load chip info
        settings = {'controller':cont}
        cont.chips = get_chip_ids(**settings)
    set_config_physics(cont, interactive)
    #flush_stale_data(cont)
    return cont

# Short-cut handle
qc = quickcontroller

