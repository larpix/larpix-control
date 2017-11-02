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

def write_register_test(settings):
    '''
    Send "config write" packet, then read the new configuration.

    Verify that:
      - no "config write" packet is returned
      - the configuration on the chip is updated to the new value(s)

    Repeat for every register on every chip.

    Will produce warnings when:
      - a "config write" packet is returned
      - the expected "config read" packet was not returned

    '''
    logger = logging.getLogger(__name__)
    logger.info('Performing write_register_test')
    port = settings['port']
    controller = larpix.Controller(port)
    controller.timeout = 0.1
    chipset = settings['chipset']
    for chipargs in chipset:
        chip = larpix.Chip(*chipargs)
        controller.chips.append(chip)
    # This new config will be written one register at a time
    new_config = larpix.Configuration()
    new_config.load('benchtest-non-defaults.json')
    for chip in controller.chips:
        chip.reads = []
        old_config = chip.config
        chip.config = new_config
        new_config_write_packets = chip.get_configuration_packets(
                larpix.Packet.CONFIG_WRITE_PACKET)
        new_config_read_packets = chip.get_configuration_packets(
                larpix.Packet.CONFIG_READ_PACKET)
        for register in range(chip.config.num_registers):
            chip.config = new_config
            # Normally I would use write_configuration but
            # I want to use serial_write_read
            bytestream = controller.get_configuration_bytestreams(chip,
                    larpix.Packet.CONFIG_WRITE_PACKET, [register])
            data = controller.serial_write_read(bytestream, 0.2)
            controller.parse_input(data)
            new_packet = new_config_write_packets[register]
            if new_packet in chip.reads:
                logger.warning(' - %s returned a config write '
                        'packet:\n    %s', str(chip), str(new_packet))
            controller.read_configuration(chip, register)
            new_packet = new_config_read_packets[register]
            if new_packet not in chip.reads:
                logger.warning(' - %s did not return the expected '
                        'config read packet.\n    Expected packet: %s'
                        '\n    chip.reads: %s', str(chip),
                        str(new_packet), str(chip.reads))
            # Return the configuration back to the default
            chip.config = old_config
            controller.write_configuration(chip)

def uart_test(settings):
    '''
    Execute the UART test on the chip.

    Check to make sure the packets are returned with no dropped packets
    and no flipped bits.

    '''
    logger = logging.getLogger(__name__)
    logger.info('Performing uart_test')
    port = settings['port']
    controller = larpix.Controller(port)
    chipset = settings['chipset']
    test_register = 47
    for chipargs in chipset:
        chip = larpix.Chip(*chipargs)
        controller.chips.append(chip)
    for chip in controller.chips:
        chip.config.test_mode = larpix.Configuration.TEST_UART
        result = controller.write_configuration(chip, registers=47, write_read=2)
        unprocessed = controller.parse_input(result)
        if unprocessed:
            logger.warning(' - %s returned garbled output: %s',
                    str(chip), str(unprocessed))
        counter = 0
        first = True
        for packet in chip.reads:
            if packet.packet_type != larpix.Packet.TEST_PACKET:
                logger.warning(' - %s returned a packet of type %s:\n    %s',
                        str(chip), str(packet.packet_type), str(packet))
                continue
            if first:
                if packet.test_counter == counter:
                    pass
                else:
                    logger.warning(' - %s first packet has counter %d',
                            str(chip), packet.test_counter)
                    counter = packet.test_counter
                    first = False
                continue
            # This line skips every third counter as per spec
            counter = counter + 1 if counter % 3 != 1 else counter + 2
            if packet.test_counter != counter:
                logger.warning(' - %s packet has counter %d, expected %d',
                        str(chip), packet.test_counter, expected_counter)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default='/dev/ttyUSB1', help='the serial port')
    args = parser.parse_args()
    setup_logger({})
    logger = logging.getLogger(__name__)
    try:
        pcb_io_test({'port':args.port})
        io_loopback_test({'port':args.port, 'chipid':1,'io_chain':0})
        read_register_test({'port':args.port, 'chipset':[(1,0)]})
        write_register_test({'port':args.port, 'chipset':[(1,0)]})
    except Exception as e:
        logger.error('Error during test', exc_info=True)
