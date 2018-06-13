'''
This module contains useful tasks for working with LArPix.

'''
from __future__ import absolute_import

import logging
import larpix.larpix as larpix
import json
from bitstring import BitArray

def setup_logger(**settings):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logfile = settings['logfile']
    handler = logging.FileHandler(logfile)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: '
            '%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def startup(**settings):
    '''
    Set the chips' configurations to a standard, quiet state.

    The configuration used is specified by the "quiet.json" file. This
    file specifies values for all configuration registers.
    '''
    logger = logging.getLogger(__name__)
    logger.info('Executing startup')
    nchips = settings['nchips']
    if 'controller' in settings:
        controller = settings['controller']
    else:
        controller = larpix.Controller(settings['port'])

    controller.use_all_chips = True
    for chip in controller.all_chips:
        chip.config.load("quiet.json")
    controller.multi_write_configuration(controller.all_chips)
    controller.use_all_chips = False

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
    chips = []
    chip_regs = [(c, 0) for c in controller.all_chips]
    controller.multi_read_configuration(chip_regs, timeout=0.1)
    for chip in controller.all_chips:
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

def simple_stats(**settings):
    '''
    Read in data from LArPix and report some simple stats.

    Stats currently are

     - mean, min, max of ADC counts by chip
     - number of ADC counts by chip
     - trigger rate by chip

    '''
    logger = logging.getLogger(__name__)
    logger.info('Executing simple_stats')
    if 'controller' in settings:
        controller = settings['controller']
    else:
        controller = larpix.Controller(settings['port'])
    if not controller.chips:
        for chip_description in settings['chipset']:
            chip = larpix.Chip(*chip_description)
            chip.config.load(settings['config'])
            controller.chips.append(chip)
            controller.write_configuration(chip)
    stored_timeout = controller.timeout
    controller.timeout = 0.1
    controller.run(settings['runtime'])
    for chip in controller.chips:
        logger.info(chip)
        adcs = list(map(lambda packet:packet.dataword, chip.reads))
        logger.info('count: %d', len(adcs))
        logger.info('rate: %f', len(adcs)/settings['runtime'])
        logger.info('mean: %f', float(sum(adcs))/len(adcs))
        logger.info('min: %d', min(adcs))
        logger.info('max: %d', max(adcs))
    controller.timeout = stored_timeout

def simple_plot(**settings):
    '''
    Read in data from LArPix and generate a few generic plots

    Plots are

     - histograms of ADC counts and timestamps (by chip)
     - ADC counts against timestamp (by chip)

    '''
    import matplotlib.pyplot as plt
    import numpy as np

    logger = logging.getLogger(__name__)
    logger.info('Executing simple_stats')
    if 'controller' in settings:
        controller = settings['controller']
    else:
        controller = larpix.Controller(settings['port'])
    if not controller.chips:
        for chip_description in settings['chipset']:
            chip = larpix.Chip(*chip_description)
            chip.config.load(settings['config'])
            controller.chips.append(chip)
            controller.write_configuration(chip)
    controller.run(settings['runtime'])
    chip_ids = controller.reads[-1].extract('chipid', type='data')
    chip_data = []
    for chip_id in set(chip_ids):
        adc_counts = controller.reads[-1].extract('adc_counts', chipid=chip_id)
        timestamps = controller.reads[-1].extract('timestamp', chipid=chip_id)
        chip_data.append({
                'chip_id': chip_id,
                'adc_counts': adc_counts,
                'timestamps': timestamps
                })

    plt.figure(1)
    adc_min = 0.9 * min(controller.reads[-1].extract('adc_counts'))
    adc_max = 1.1 * max(controller.reads[-1].extract('adc_counts'))
    adc_bins = np.linspace(adc_min, adc_max, 25)
    timestamp_min = 0.9 * min(controller.reads[-1].extract('timestamp'))
    timestamp_max = 1.1 * max(controller.reads[-1].extract('timestamp'))
    timestamp_bins = np.linspace(timestamp_min, timestamp_max, 25)

    plt.subplot(311)
    plt.xlabel('Timestamp')
    plt.ylabel('ADC value')
    plt.grid(True)

    plt.subplot(312)
    plt.xlabel('ADC value')

    plt.subplot(313)
    plt.xlabel('Timestamp')
    for data in chip_data:
        plt.subplot(311)
        plt.plot(data['timestamps'], data['adc_counts'], 'o',
                label='Chip: %d' % data['chip_id'])

        plt.subplot(312)
        plt.hist(data['adc_counts'], bins=adc_bins, histtype='step')

        plt.subplot(313)
        plt.hist(data['timestamps'], bins=timestamp_bins, histtype='step')

    plt.subplot(311).legend()
    plt.show()

if __name__ == '__main__':
    import argparse
    import sys
    tasks = {
            'simple_stats': simple_stats,
            'get_chip_ids': get_chip_ids,
            'startup': startup,
            'simple_plot': simple_plot,
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
    setup_logger(**settings)
    logger = logging.getLogger(__name__)
    logger.info('-'*60)
    logger.info(args.message)
    try:
        for task in args.task:
            tasks[task](**settings)
    except Exception as e:
        logger.error('Error during task', exc_info=True)
