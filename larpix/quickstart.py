'''
Quickstart commands for test boards
'''

from __future__ import absolute_import
import larpix.larpix as larpix
from larpix.tasks import get_chip_ids

## For interactive mode
import sys
VERSION = sys.version_info
if VERSION[0] < 3:
    input = raw_input
##


#List of LArPix test board configurations
board_info_list = [
    {'name':'unknown',
     'chip_list':[(chip_id,0) for chip_id in range(0,256)],},
    {'name':'pcb-5',
     'chip_list':[(246,0),(245,0),(252,0),(243,0)],},
    {'name':'pcb-4',
     'chip_list':[(207,0),(63,0),(250,0),(249,0)],},
    {'name':'pcb-1',
     'chip_list':[(246,0),(245,0),(252,0),(243,0)],},
    {'name':'pcb-10',
     'chip_list':[(3,0),(5,0),(6,0),(9,0),(10,0),(12,0),
                  (63,0),(60,0),(58,0),(54,0),(57,0),(53,0),(51,0),(48,0),
                  (80,0),(83,0),(85,0),(86,0),(89,0),(90,0),(92,0),(95,0),
                  (99,0),(101,0),(102,0),(105,0),(106,0),(108,0)]}
]

#Create handy map by board name
board_info_map = dict([(elem['name'],elem) for elem in board_info_list])

def create_controller(timeout=0.01, io=None):
    '''Create a default controller'''
    c = larpix.Controller(timeout=timeout)
    c.io = io
    return c

def init_controller(controller, board='pcb-5'):
    '''Initialize controller'''
    if not board in board_info_map.keys():
        board = 'unknown'
    board_info = board_info_map[board]
    for chip_info in board_info['chip_list']:
        controller.chips.append( larpix.Chip(chip_info[0],chip_info[1]) )
    controller.board_info = board_info
    return controller

def silence_chips(controller, interactive):
    '''Silence all chips in controller'''
    #for _ in controller.chips:
    for chip in controller.chips:
        if interactive:
            print('Silencing chip %d' % chip.chip_id)
        chip.config.global_threshold = 255
        controller.write_configuration(chip,32)
        if interactive:
            input('Just silenced chip %d. <enter> when ready.\n' % chip.chip_id)
    return

def disable_chips(controller):
    '''Silence all chips in controller'''
    #for _ in controller.chips:
    for chip in controller.chips:
        chip.config.disable_channels()
        controller.write_configuration(chip,range(52,56))
    return

def set_config_physics(controller, interactive):
    '''Set the chips for the default physics configuration'''
    #import time
    for chip in controller.chips:
        '''if not board is None:
            try:
                chip.config.load('physics-%s-c%d.json' % (board, chip.chip_id))
            except Exception as e:
                print('failed to load chip specific config - error: %s' % e)
                chip.config.load('physics.json')
        else:
            chip.config.load('physics.json')
        controller.write_configuration(chip)'''
        if interactive:
            x = input('Configuring chip %d. <enter> to continue, q to quit' % chip.chip_id)
            if x == 'q':
                break
        chip.config.internal_bypass = 1
        controller.write_configuration(chip,33)
        chip.config.periodic_reset = 1
        controller.write_configuration(chip,47)
        chip.config.global_threshold = 60
        controller.write_configuration(chip,32)
        chip.config.reset_cycles = 4096
        controller.write_configuration(chip,range(60,63))
        #time.sleep(2)
        print('configured chip %d' % chip.chip_id)
    return

def flush_stale_data(controller):
    '''Read and discard buffer contents'''
    controller.run(1,'flush_buffer')
    controller.reads = []
    return
    
def quickcontroller(board='pcb-1', interactive=False, io=None):
    '''Quick jump through all controller creation and config steps'''
    if io is None:
        port = larpix.SerialPort.guess_port()
        io = larpix.SerialPort(port=port, baudrate=1000000,
                timeout=0.01)
    larpix.enable_logger()
    cont = create_controller(io=io)
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

