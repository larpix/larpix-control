'''
This module contains useful tasks for working with LArPix.

'''
from __future__ import absolute_import

import logging
import larpix.larpix as larpix
import json
from bitstring import BitArray

def setup_logger(settings):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logfile = settings['logfile']
    handler = logging.FileHandler(logfile)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: '
            '%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def startup(settings):
    '''
    Set the chips' configurations to a standard, quiet state.

    The configuration used is specified by the "quiet.json" file. This
    file specifies values for all configuratoin registers.
    '''
    logger = logging.getLogger(__name__)
    logger.info('Executing startup')
    controller = larpix.Controller(settings['port'])
    controller.init_chips()
    nchips = settings['nchips']
    for _ in range(nchips):
        for chip in controller.chips:
            chip.config.load("quiet.json")
            controller.write_configuration(chip)

def get_chip_ids(settings):
    '''
    Return a list of Chip objects representing the chips on the board.

    Checks if a chip is present by adjusting one channel's pixel trim
    threshold and checking to see that the correct configuration is read
    back in.
    '''
    logger = logging.getLogger(__name__)
    logger.info('Executing get_chip_ids')
    controller = larpix.Controller(settings['port'])
    controller.timeout=0.1
    controller.init_chips()
    chips = []
    for chip in controller.chips:
        controller.read_configuration(chip, 0, timeout=0.1)
        read_packet = chip.reads[-1]
        if read_packet.register_data != 0:
            chips.append(chip)
            logger.info('Found chip %s' % chip)
    return chips

def simple_stats(settings):
    '''
    Read in data from LArPix and report some simple stats.

    Stats currently are

     - mean, min, max of ADC counts by chip
     - number of ADC counts by chip
     - trigger rate by chip

    '''
    logger = logging.getLogger(__name__)
    logger.info('Executing simple_stats')
    controller = larpix.Controller(settings['port'])
    controller.timeout = 0.1
    for chip_description in settings['chipset']:
        chip = larpix.Chip(*chip_description)
        chip.config.load(settings['config'])
        controller.chips.append(chip)
        controller.write_configuration(chip)
    controller.run(settings['runtime'])
    for chip in controller.chips:
        logger.info(chip)
        adcs = list(map(lambda packet:packet.dataword, chip.reads))
        logger.info('count: %d', len(adcs))
        logger.info('rate: %f', len(adcs)/settings['runtime'])
        logger.info('mean: %f', float(sum(adcs))/len(adcs))
        logger.info('min: %d', min(adcs))
        logger.info('max: %d', max(adcs))


if __name__ == '__main__':
    import argparse
    import sys
    tasks = {
            'simple_stats': simple_stats,
            'get_chip_ids': get_chip_ids,
            'startup': startup,
            }
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
    parser.add_argument('-n', '--nchips', type=int,
            help='number of chips on the board')
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
            'nchips': args.nchips,
            'runtime': args.runtime,
            }
    setup_logger(settings)
    logger = logging.getLogger(__name__)
    logger.info('-'*60)
    logger.info(args.message)
    try:
        for task in args.task:
            tasks[task](settings)
    except Exception as e:
        logger.error('Error during task', exc_info=True)
