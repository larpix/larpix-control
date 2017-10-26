'''
This module contains a set of bench test scripts for the LArPix chip.

'''
import logging
import larpix
from bitstring import BitArray

def setup_logger(settings):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logfile = settings.get('logfile', 'benchtest.log')
    handler = logging.FileHandler(logfile)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: '
            '%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def pcb_io_test(settings):
    '''
    Send commands to PCB.

    Probe to verify commands are received. Check for unwanted noise,
    ringing, and reflections.

    '''
    logger = logging.getLogger(__name__)
    logger.info('Performing pcb_io_test')
    port = settings['port']
    controller = larpix.Controller(port)
    packet = larpix.Packet()
    packet.bits = BitArray([1, 0] * 27)
    bytestream = [b's' + packet.bytes() + b'\x00q']
    controller.serial_write(bytestream)

def io_loopback_test(settings):
    '''
    Verify that packet with false chip ID returns to the control system.

    Send packet through daisy chain of LArPix chips but provide the
    wrong chip ID. Each chip should pass on the packet to the next one,
    so that the packet comes out at the end as output.

    '''
    logger = logging.getLogger(__name__)
    logger.info('Performing io_loopback_test')
    port = settings['port']
    controller = larpix.Controller(port)
    chipid = settings['chipid']
    io_chain = settings['io_chain']
    chip = larpix.Chip(chipid, io_chain)
    controller.chips.append(chip)
    packet = larpix.Packet()
    packet.packet_type = larpix.Packet.CONFIG_READ_PACKET
    packet.chipid = chip.chip_id
    packet.register_address = 10
    packet.register_data = 25
    packet.assign_parity()
    bytestream = [controller.format_UART(chip, packet)]
    data = controller.serial_write_read(bytestream, 1)
    controller.parse_input(data)
    if len(chip.reads) > 0:
        returned_packet_str = str(chip.reads[0])
        logger.info(' - Received packet %s', returned_packet_str)
    else:
        logger.warning(' - Did not receive any packets')


def read_register_test(settings):
    '''
    Send "config read" packet and read back the configuration.

    Verify that the packet returns to the control system with the
    expected data. Repeat for every register on every chip.

    '''
    logger = logging.getLogger(__name__)
    logger.info('Performing read_register_test')
    port = settings['port']
    controller = larpix.Controller(port)
    chipset = settings['chipset']
    for chipargs in chipset:
        chip = larpix.Chip(*chipargs)
        controller.chips.append(chip)
    for chip in controller.chips:
        remainder = controller.read_configuration(chip)
        if remainder != b'':
            logger.warning(' - %s returned invalid bytes: %s',
                    str(chip), str(remainder))
        # The chip configuration should be default, so the config we
        # have recorded in software is the same as the expected
        # configuration of the actual chips
        expected_packets = chip.get_configuration_packets(
                larpix.Packet.CONFIG_READ_PACKET)
        actual_packets = chip.reads
        missing_packets = [p for p in expected_packets if p not in
                actual_packets]
        extra_packets = [p for p in actual_packets if p not in
                expected_packets]
        if missing_packets:
            logger.warning(' - %s is missing packets: \n    %s',
                    str(chip), '\n    '.join(map(str, missing_packets)))
        if extra_packets:
            logger.warning(' - %s has extra packets: \n    %s',
                    str(chip), '\n    '.join(map(str, extra_packets)))


if __name__ == '__main__':
    setup_logger({})
    logger = logging.getLogger(__name__)
    try:
        pcb_io_test({'port':'/dev/ttyUSB1'})
        io_loopback_test({'port':'/dev/ttyUSB1', 'chipid':1,'io_chain':0})
        read_register_test({'port':'/dev/ttyUSB1', 'chipset':[(1,0)]})
    except Exception as e:
        logger.error('Error during test', exc_info=True)
