'''
A module to control the LArPix chip.

'''

import time
import serial
from bitstring import BitArray, Bits

class Chip(object):
    '''
    Represents one LArPix chip and helps with configuration and packet
    generation.

    '''
    num_channels = 32
    def __init__(self, chip_id, io_chain):
        self.chip_id = chip_id
        self.io_chain = io_chain
        self.data_to_send = []
        self.config = Configuration()
        self.reads = []

    def get_configuration_packets(self, packet_type):
        conf = self.config
        packets = [Packet() for _ in range(Configuration.num_registers)]
        packet_register_data = conf.all_data()
        for i, (packet, data) in enumerate(zip(packets, packet_register_data)):
            packet.packet_type = packet_type
            packet.chipid = self.chip_id
            packet.register_address = i
            packet.register_data = data
            packet.assign_parity()
        return packets

class Configuration(object):
    '''
    Represents the desired configuration state of a LArPix chip.

    '''
    num_registers = 63
    pixel_trim_threshold_addresses = list(range(0, 32))
    global_threshold_address = 32
    csa_gain_and_bypasses_address = 33
    csa_bypass_select_addresses = list(range(34, 38))
    csa_monitor_select_addresses = list(range(38, 42))
    csa_testpulse_enable_addresses = list(range(42, 46))
    csa_testpulse_dac_amplitude_address = 46
    test_mode_xtrig_reset_diag_address = 47
    sample_cycles_address = 48
    test_burst_length_addresses = [49, 50]
    adc_burst_length_address = 51
    channel_mask_addresses = list(range(52, 56))
    external_trigger_mask_addresses = list(range(56, 60))
    reset_cycles_addresses = [60, 61, 62]

    TEST_OFF = 0x0
    TEST_UART = 0x1
    TEST_FIFO = 0x2
    def __init__(self):
        self.pixel_trim_thresholds = [0x10] * Chip.num_channels
        self.global_threshold = 0x10
        self.csa_gain = 1
        self.csa_bypass = 0
        self.internal_bypass = 1
        self.csa_bypass_select = [0] * Chip.num_channels
        self.csa_monitor_select = [1] * Chip.num_channels
        self.csa_testpulse_enable = [0] * Chip.num_channels
        self.csa_testpulse_dac_amplitude = 0
        self.test_mode = Configuration.TEST_OFF
        self.cross_trigger_mode = 0
        self.periodic_reset = 0
        self.fifo_diagnostic = 0
        self.sample_cycles = 1
        self.test_burst_length = 0x00FF
        self.adc_burst_length = 0
        self.channel_mask = [0] * Chip.num_channels
        self.external_trigger_mask = [1] * Chip.num_channels
        self.reset_cycles = 0x001000

    def enable_channels(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.channel_mask[channel] = 0

    def disable_channels(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.channel_mask[channel] = 1

    def enable_normal_operation(self):
        #TODO Ask Dan what this means
        pass

    def enable_external_trigger(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.external_trigger_mask[channel] = 0

    def disable_external_trigger(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.external_trigger_mask[channel] = 1

    def enable_testpulse(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.csa_testpulse_enable[channel] = 1

    def disable_testpulse(self, list_of_channels=None):
        if list_of_channels is None:
            list_of_channels = range(Chip.num_channels)
        for channel in list_of_channels:
            self.csa_testpulse_enable[channel] = 0

    def enable_analog_monitor(self, channel):
        self.csa_monitor_select[channel] = 0

    def disable_analog_monitor(self):
        self.csa_monitor_select = [1] * Chip.num_channels

    def all_data(self):
        bits = []
        num_channels = Chip.num_channels
        for channel in range(num_channels):
            bits.append(self.trim_threshold_data(channel))
        bits.append(self.global_threshold_data())
        bits.append(self.csa_gain_and_bypasses_data())
        for chunk in range(4):
            bits.append(self.csa_bypass_select_data(chunk))
        for chunk in range(4):
            bits.append(self.csa_monitor_select_data(chunk))
        for chunk in range(4):
            bits.append(self.csa_testpulse_enable_data(chunk))
        bits.append(self.csa_testpulse_dac_amplitude_data())
        bits.append(self.test_mode_xtrig_reset_diag_data())
        bits.append(self.sample_cycles_data())
        bits.append(self.test_burst_length_data(0))
        bits.append(self.test_burst_length_data(1))
        bits.append(self.adc_burst_length_data())
        for chunk in range(4):
            bits.append(self.channel_mask_data(chunk))
        for chunk in range(4):
            bits.append(self.external_trigger_mask_data(chunk))
        bits.append(self.reset_cycles_data(0))
        bits.append(self.reset_cycles_data(1))
        bits.append(self.reset_cycles_data(2))
        return bits

    def _to8bits(self, number):
        return Bits('uint:8=' + str(number))

    def trim_threshold_data(self, channel):
        return self._to8bits(self.pixel_trim_thresholds[channel])

    def global_threshold_data(self):
        return self._to8bits(self.global_threshold)

    def csa_gain_and_bypasses_data(self):
        return Bits('0b0000') + [self.internal_bypass, 0,
                self.csa_bypass, self.csa_gain]

    def csa_bypass_select_data(self, chunk):
        if chunk == 0:
            return Bits(self.csa_bypass_select[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.csa_bypass_select[high_bit:low_bit:-1])

    def csa_monitor_select_data(self, chunk):
        if chunk == 0:
            return Bits(self.csa_monitor_select[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.csa_monitor_select[high_bit:low_bit:-1])

    def csa_testpulse_enable_data(self, chunk):
        if chunk == 0:
            return Bits(self.csa_testpulse_enable[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.csa_testpulse_enable[high_bit:low_bit:-1])

    def csa_testpulse_dac_amplitude_data(self):
        return self._to8bits(self.csa_testpulse_dac_amplitude)

    def test_mode_xtrig_reset_diag_data(self):
        toReturn = BitArray([0, 0, 0, self.fifo_diagnostic,
            self.periodic_reset,
            self.cross_trigger_mode])
        toReturn.append('uint:2=' + str(self.test_mode))
        return toReturn

    def sample_cycles_data(self):
        return self._to8bits(self.sample_cycles)

    def test_burst_length_data(self, chunk):
        bits = Bits('uint:16=' + str(self.test_burst_length))
        if chunk == 0:
            return bits[8:]
        elif chunk == 1:
            return bits[:8]

    def adc_burst_length_data(self):
        return self._to8bits(self.adc_burst_length)

    def channel_mask_data(self, chunk):
        if chunk == 0:
            return Bits(self.channel_mask[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.channel_mask[high_bit:low_bit:-1])

    def external_trigger_mask_data(self, chunk):
        if chunk == 0:
            return Bits(self.external_trigger_mask[7::-1])
        else:
            high_bit = (chunk + 1) * 8 - 1
            low_bit = chunk * 8 - 1
            return Bits(self.external_trigger_mask[high_bit:low_bit:-1])

    def reset_cycles_data(self, chunk):
        bits = Bits('uint:24=' + str(self.reset_cycles))
        if chunk == 0:
            return bits[16:]
        elif chunk == 1:
            return bits[8:16]
        elif chunk == 2:
            return bits[:8]


class Controller(object):
    '''
    Controls a collection of LArPix Chip objects.

    '''
    start_byte = b'\x73'
    stop_byte = b'\x71'
    def __init__(self, port):
        self.chips = []
        self.port = port
        self.baudrate = 1000000
        self.timeout = 1
        self.max_write = 8192
        self._test_mode = False

    def get_chip(self, chip_id, io_chain):
        for chip in self.chips:
            if chip.chip_id == chip_id and chip.io_chain == io_chain:
                return chip
        raise ValueError('Could not find chip (%d, %d)' % (chip_id,
            io_chain))

    def serial_read(self, timelimit):
        data_in = []
        start = time.time()
        with serial.Serial(self.port, baudrate=self.baudrate,
                timeout=self.timeout) as serial_in:
            while time.time() - start < timelimit:
                stream = serial_in.read(self.max_write)
                if len(stream) > 0:
                    data_in.append(stream)
        return data_in

    def serial_write(self, bytestreams):
        with serial.Serial(self.port, baudrate=self.baudrate,
                timeout=self.timeout) as output:
            for bytestream in bytestreams:
                output.write(bytestream)

    def write_configuration(self, chip, registers=None):
        if registers is None:
            registers = list(range(Configuration.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        # The configuration must be sent one register at a time
        configuration_packets = \
            chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET);
        for i in range(len(configuration_packets)-1, -1, -1):
            if i not in registers:
                del configuration_packets[i]
        formatted_packets = [self.format_UART(chip, p) for p in
                configuration_packets]
        bytestreams = self.format_bytestream(formatted_packets)
        if self._test_mode:
            return bytestreams
        else:
            self.serial_write(bytestreams)
            return

    def run_testpulse(self, list_of_channels):
        return

    def run_fifo_test(self):
        return

    def run_analog_monitor_teest(self):
        return

    def format_UART(self, chip, packet):
        packet_bytes = packet.bytes()
        daisy_chain_byte = (4 + Bits('uint:4=' + str(chip.io_chain))).bytes
        formatted_packet = (Controller.start_byte + packet_bytes +
                daisy_chain_byte + Controller.stop_byte)
        return formatted_packet

    def parse_input(self, bytestream):
        packet_size = 10
        start_byte = Controller.start_byte[0]
        stop_byte = Controller.stop_byte[0]
        metadata_byte_index = 8
        data_bytes = slice(1,8)
        # parse the bytestream into Packets + metadata
        byte_packets = []
        current_stream = bytestream
        while len(current_stream) >= packet_size:
            if (current_stream[0] == start_byte and
                    current_stream[packet_size-1] == stop_byte):
                metadata = current_stream[metadata_byte_index]
                # This is necessary because of differences between
                # Python 2 and Python 3
                if isinstance(metadata, int):  # Python 3
                    code = 'uint:8='
                elif isinstance(metadata, str):  # Python 2
                    code = 'bytes:1='
                byte_packets.append((Bits(code + str(metadata)),
                    Packet(current_stream[data_bytes])))
                current_stream = current_stream[packet_size:]
            else:
                # Throw out everything between here and the next start byte.
                # Note: start searching after byte 0 in case it's
                # already a start byte
                next_start_index = current_stream[1:].find(start_byte)
                current_stream = current_stream[1:][next_start_index:]
        # assign each packet to the corresponding Chip
        for byte_packet in byte_packets:
            io_chain = byte_packet[0][4:].uint
            packet = byte_packet[1]
            chip_id = packet.chipid
            self.get_chip(chip_id, io_chain).reads.append(packet)
        return current_stream  # (the remainder that wasn't read in)

    def format_bytestream(self, formatted_packets):
        bytestreams = []
        current_bytestream = bytes()
        for packet in formatted_packets:
            if len(current_bytestream) + len(packet) < self.max_write:
                current_bytestream += packet
            else:
                bytestreams.append(current_bytestream)
                current_bytestream = bytes()
                current_bytestream += packet
        bytestreams.append(current_bytestream)
        return bytestreams



class Packet(object):
    '''
    A single 54-bit LArPix UART data packet.

    '''
    size = 54
    num_bytes = 7
    # These ranges are reversed from the bit addresses given in the
    # LArPix datasheet because BitArray indexing is big-endian but we
    # transmit data little-endian-ly. E.g.:
    # >>> x = BitArray('0b00')
    # >>> x[0:] = bin(2)  # ('0b10')
    # >>> x[0]  # returns True (1)
    # Another way to think of it is BitArray indexing reads the
    # bitstream from 0:N but all the LArPix datasheet indexing goes from
    # N:0.
    packet_type_bits = slice(52, 54)
    chipid_bits = slice(44, 52)
    parity_bit = 0
    parity_calc_bits = slice(1, 53)
    channel_id_bits = slice(37, 44)
    timestamp_bits = slice(13, 37)
    dataword_bits = slice(3, 13)
    fifo_half_bit = 2
    fifo_full_bit = 1
    register_address_bits = slice(36, 44)
    register_data_bits = slice(28, 36)
    config_unused_bits = slice(1, 28)
    test_bits_11_0 = slice(1, 13)
    test_bits_15_12 = slice(41, 44)

    TEST_PACKET = Bits('0b00')
    DATA_PACKET = Bits('0b01')
    CONFIG_WRITE_PACKET = Bits('0b10')
    CONFIG_READ_PACKET = Bits('0b11')

    def __init__(self, bytestream=None):
        self._bit_padding = Bits('0b00')
        if bytestream is None:
            self.bits = BitArray(Packet.size)
            return
        elif len(bytestream) == Packet.num_bytes:
            # Parse the bytestream. Remember that bytestream[0] goes at
            # the 'end' of the BitArray
            reversed_bytestream = bytestream[::-1]
            bits_with_padding = BitArray(bytes=reversed_bytestream)
            self.bits = bits_with_padding[len(self._bit_padding):]
        else:
            raise ValueError('Invalid number of bytes: %s' %
                    len(bytestream))

    def __eq__(self, other):
        return self.bits == other.bits

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        return 'Packet: bit 53->' + self.bits.bin + '<-bit 0'

    def __repr__(self):
        return 'Packet(' + str(self.bytes()) + ')'

    def bytes(self):
        # Here's the only other place we have to deal with the
        # endianness issue by reversing the order
        padded_output = self._bit_padding + self.bits
        bytes_output = padded_output.bytes
        return bytes_output[::-1]

    @property
    def packet_type(self):
        return self.bits[Packet.packet_type_bits]

    @packet_type.setter
    def packet_type(self, value):
        self.bits[Packet.packet_type_bits] = value

    @property
    def chipid(self):
        return self.bits[Packet.chipid_bits].uint

    @chipid.setter
    def chipid(self, value):
        self.bits[Packet.chipid_bits] = value

    @property
    def parity_bit_value(self):
        return int(self.bits[Packet.parity_bit])

    @parity_bit_value.setter
    def parity_bit_value(self, value):
        self.bits[Packet.parity_bit] = value

    def compute_parity(self):
        return 1 - (self.bits[Packet.parity_calc_bits].count(True) % 2)

    def assign_parity(self):
        self.parity_bit_value = self.compute_parity()

    def has_valid_parity(self):
        return self.parity_bit_value == self.compute_parity()

    @property
    def register_address(self):
        return self.bits[Packet.register_address_bits].uint

    @register_address.setter
    def register_address(self, value):
        self.bits[Packet.register_address_bits] = value

    @property
    def register_data(self):
        return self.bits[Packet.register_data_bits].uint

    @register_data.setter
    def register_data(self, value):
        self.bits[Packet.register_data_bits] = value

