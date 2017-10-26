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
    returned_packet_str = str(chip.reads[0])
    logger.info(' - Received packet %s', returned_packet_str)

if __name__ == '__main__':
    setup_logger({})
    pcb_io_test({'port':'/dev/ttyUSB1'})
    io_loopback_test({'port':'/dev/ttyUSB1', 'chipid':1,'io_chain':0})
