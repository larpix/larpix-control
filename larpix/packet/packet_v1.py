from bitarray import bitarray
import struct

from .. import bitarrayhelper as bah
from ..key import Key

class Packet_v1(object):
    '''
    A single 54-bit LArPix UART data packet.

    LArPix Packet objects have attributes for inspecting and modifying
    the contents of the packet.

    Internally, packets are represented as an array of bits, and the
    different attributes use Python "properties" to seamlessly convert
    between the bits representation and a more intuitive integer
    representation. The bits representation can be inspected with the
    ``bits`` attribute.

    Packet objects do not restrict you from adjusting an attribute for an
    inappropriate packet type. For example, you can create a data packet and
    then set ``packet.register_address = 5``. This will adjust the packet
    bits corresponding to a configuration packet's "register\_address"
    region, which is probably not what you want for your data packet.

    Packets have a parity bit which enforces odd parity, i.e. the sum of
    all the individual bits in a packet must be an odd number. The parity
    bit can be accessed as above using the ``parity_bit_value`` attribute.
    The correct parity bit can be computed using ``compute_parity()``,
    and the validity of a packet's parity can be checked using
    ``has_valid_parity()``. When constructing a new packet, the correct
    parity bit can be assigned using ``assign_parity()``.

    Individual packets can be printed to show a human-readable
    interpretation of the packet contents. The printed version adjusts its
    output based on the packet type, so a data packet will show the data
    word, timestamp, etc., while a configuration packet will show the register
    address and register data.

    '''
    asic_version = 1
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
    parity_calc_bits = slice(1, 54)
    channel_id_bits = slice(37, 44)
    timestamp_bits = slice(13, 37)
    dataword_bits = slice(3, 13)
    fifo_half_bit = 2
    fifo_full_bit = 1
    register_address_bits = slice(36, 44)
    register_data_bits = slice(28, 36)
    config_unused_bits = slice(1, 28)
    test_counter_bits_11_0 = slice(1, 13)
    test_counter_bits_15_12 = slice(40, 44)

    DATA_PACKET = bitarray('00')
    TEST_PACKET = bitarray('01')
    CONFIG_WRITE_PACKET = bitarray('10')
    CONFIG_READ_PACKET = bitarray('11')
    _bit_padding = bitarray('00')

    def __init__(self, bytestream=None):
        if bytestream is None:
            self.bits = bitarray(self.size)
            self.bits.setall(False)
            return
        elif len(bytestream) == self.num_bytes:
            # Parse the bytestream. Remember that bytestream[0] goes at
            # the 'end' of the BitArray
            reversed_bytestream = bytestream[::-1]
            self.bits = bitarray()
            self.bits.frombytes(reversed_bytestream)
            # Get rid of the padding (now at the beginning of the
            # bitstream because of the reverse order)
            self.bits = self.bits[2:]
        else:
            raise ValueError('Invalid number of bytes: %s' %
                    len(bytestream))

    def __eq__(self, other):
        return self.bits == other.bits

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        string = '[ '
        string += 'Chip key: {} | '.format(self.chip_key)
        if hasattr(self, 'direction'):
            string += 'Direction: {}'.format(self.direction)
            string += ' | '
        ptype = self.packet_type
        if ptype == Packet_v1.TEST_PACKET:
            string += 'Test | '
            string += 'Counter: %d | ' % self.test_counter
        elif ptype == Packet_v1.DATA_PACKET:
            string += 'Data | '
            string += 'Channel: %d | ' % self.channel_id
            string += 'Timestamp: %d | ' % self.timestamp
            string += 'ADC data: %d | ' % self.dataword
            string += 'FIFO Half: %s | ' % bool(self.fifo_half_flag)
            string += 'FIFO Full: %s | ' % bool(self.fifo_full_flag)
        elif (ptype == Packet_v1.CONFIG_READ_PACKET or ptype ==
                Packet_v1.CONFIG_WRITE_PACKET):
            if ptype == Packet_v1.CONFIG_READ_PACKET:
                string += 'Config read | '
            else:
                string += 'Config write | '
            string += 'Register: %d | ' % self.register_address
            string += 'Value: % d | ' % self.register_data
        first_splitter = string.find('|')
        string = (string[:first_splitter] + '| Chip: %d ' % self.chipid +
                string[first_splitter:])
        string += ('Parity: %d (valid: %s) ]' %
                (self.parity_bit_value, self.has_valid_parity()))
        return string

    def __repr__(self):
        return 'Packet_v1(' + str(self.bytes()) + ')'

    def bytes(self):
        '''
        Construct the bytes that make up the packet.

        Byte 0 is the first byte that would be sent out and contains the
        first 8 bits of the packet (i.e. packet type and part of the
        chip ID).

        *Note*: The internal bits representation of the packet has a
        different endian-ness compared to the output of this method.

        '''
        # Here's the only other place we have to deal with the
        # endianness issue by reversing the order
        padded_output = self._bit_padding + self.bits
        bytes_output = padded_output.tobytes()
        return bytes_output[::-1]

    def export(self):
        '''Return a dict representation of this Packet.'''
        type_map = {
                self.TEST_PACKET.to01(): 'test',
                self.DATA_PACKET.to01(): 'data',
                self.CONFIG_WRITE_PACKET.to01(): 'config write',
                self.CONFIG_READ_PACKET.to01(): 'config read'
                }
        d = {}
        d['asic_version'] = self.asic_version
        d['chip_key'] = str(self.chip_key) if self.chip_key else None
        d['bits'] = self.bits.to01()
        d['type_str'] = type_map[self.packet_type.to01()]
        d['type'] = bah.touint(self.packet_type)
        d['chipid'] = self.chipid
        d['parity'] = self.parity_bit_value
        d['valid_parity'] = self.has_valid_parity()
        ptype = self.packet_type
        if ptype == Packet_v1.TEST_PACKET:
            d['counter'] = self.test_counter
        elif ptype == Packet_v1.DATA_PACKET:
            d['channel'] = self.channel_id
            d['timestamp'] = self.timestamp
            d['adc_counts'] = self.dataword
            d['fifo_half'] = bool(self.fifo_half_flag)
            d['fifo_full'] = bool(self.fifo_full_flag)
        elif (ptype == Packet_v1.CONFIG_READ_PACKET or ptype ==
                Packet_v1.CONFIG_WRITE_PACKET):
            d['register'] = self.register_address
            d['value'] = self.register_data
        return d

    def from_dict(self, d):
        ''' Inverse of export - modify packet based on dict '''
        if not d['asic_version'] == self.asic_version:
            raise ValueError('invalid asic version {}'.format(d['asic_version']))
        if 'type' in d and d['type'] not in [bah.touint(packet_type) for packet_type in \
            (Packet_v1.DATA_PACKET, Packet_v1.TEST_PACKET, Packet_v1.CONFIG_WRITE_PACKET, Packet_v1.CONFIG_READ_PACKET)]:
            raise ValueError('invalid packet type for Packet_v2')
        for key, value in d.items():
            if key in ('type_str', 'valid_parity'):
                continue
            elif key == 'bits':
                self.bits = bitarray(value)
            elif key == 'type':
                self.packet_type = value
            elif key == 'register':
                self.register_address = value
            elif key == 'value':
                self.register_data = value
            elif key == 'adc_counts':
                self.dataword = value
            elif key == 'parity':
                self.parity_bit_value = value
            elif key == 'counter':
                self.test_counter = value
            elif key == 'channel':
                self.channel_id = value
            elif key == 'fifo_half':
                self.fifo_half_flag = value
            elif key == 'fifo_full':
                self.fifo_full_flag = value
            else:
                setattr(self, key, value)

    @property
    def chip_key(self):
        if hasattr(self, '_chip_key'):
            return self._chip_key
        if self.io_group is None or self.io_channel is None:
            return None
        self._chip_key = Key(self.io_group, self.io_channel, self.chipid)
        return self._chip_key

    @chip_key.setter
    def chip_key(self, value):
        # remove cached key
        if hasattr(self, '_chip_key'):
            del self._chip_key
        if value is None:
            self.io_channel = None
            self.io_group = None
            return
        if isinstance(value, Key):
            self.io_group = value.io_group
            self.io_channel = value.io_channel
            self.chipid = value.chip_id
            return
        # try again by casting as a Key
        self.chip_key = Key(value)

    @property
    def io_group(self):
        if hasattr(self, '_io_channel'):
            return self._io_group
        return None

    @io_group.setter
    def io_group(self, value):
        if hasattr(self, '_chip_key'):
            # remove cached key
            del self._chip_key
        if value is None:
            if hasattr(self, '_io_group'):
                del self._io_group
            return
        # no value validation!
        self._io_group = value

    @property
    def io_channel(self):
        if hasattr(self, '_io_channel'):
            return self._io_channel
        return None

    @io_channel.setter
    def io_channel(self, value):
        if hasattr(self, '_chip_key'):
            # remove cached key
            del self._chip_key
        if value is None:
            if hasattr(self, '_io_channel'):
                del self._io_channel
            return
        # no value validation!
        self._io_channel = value

    @property
    def packet_type(self):
        return self.bits[self.packet_type_bits]

    @packet_type.setter
    def packet_type(self, value):
        self.bits[self.packet_type_bits] = bah.fromuint(value,
                self.packet_type_bits)

    @property
    def chipid(self):
        return bah.touint(self.bits[self.chipid_bits])

    @chipid.setter
    def chipid(self, value):
        if hasattr(self, '_chip_key'):
            # remove cached key
            del self._chip_key
        self.bits[self.chipid_bits] = bah.fromuint(value,
                self.chipid_bits)

    @property
    def chip_id(self):
        # additional handle to match Packet_v2 name
        return self.chipid

    @chip_id.setter
    def chip_id(self, value):
        self.chipid = value

    @property
    def parity_bit_value(self):
        return int(self.bits[self.parity_bit])

    @parity_bit_value.setter
    def parity_bit_value(self, value):
        self.bits[self.parity_bit] = bool(value)

    def compute_parity(self):
        return 1 - (self.bits[self.parity_calc_bits].count(True) % 2)

    def assign_parity(self):
        self.parity_bit_value = self.compute_parity()

    def has_valid_parity(self):
        return self.parity_bit_value == self.compute_parity()

    @property
    def channel_id(self):
        return bah.touint(self.bits[self.channel_id_bits])

    @channel_id.setter
    def channel_id(self, value):
        self.bits[self.channel_id_bits] = bah.fromuint(value,
                self.channel_id_bits)

    @property
    def timestamp(self):
        return bah.touint(self.bits[self.timestamp_bits])

    @timestamp.setter
    def timestamp(self, value):
        self.bits[self.timestamp_bits] = bah.fromuint(value,
                self.timestamp_bits)

    @property
    def dataword(self):
        ostensible_value = bah.touint(self.bits[self.dataword_bits])
        # TODO fix in LArPix v2
        return ostensible_value - (ostensible_value % 2)

    @dataword.setter
    def dataword(self, value):
        self.bits[self.dataword_bits] = bah.fromuint(value,
                self.dataword_bits)

    @property
    def fifo_half_flag(self):
        return int(self.bits[self.fifo_half_bit])

    @fifo_half_flag.setter
    def fifo_half_flag(self, value):
        self.bits[self.fifo_half_bit] = bool(value)

    @property
    def fifo_full_flag(self):
        return int(self.bits[self.fifo_full_bit])

    @fifo_full_flag.setter
    def fifo_full_flag(self, value):
        self.bits[self.fifo_full_bit] = bool(value)

    @property
    def register_address(self):
        return bah.touint(self.bits[self.register_address_bits])

    @register_address.setter
    def register_address(self, value):
        self.bits[self.register_address_bits] = bah.fromuint(value,
                self.register_address_bits)

    @property
    def register_data(self):
        return bah.touint(self.bits[self.register_data_bits])

    @register_data.setter
    def register_data(self, value):
        self.bits[self.register_data_bits] = bah.fromuint(value,
                self.register_data_bits)

    @property
    def test_counter(self):
        return bah.touint(self.bits[self.test_counter_bits_15_12] +
                self.bits[self.test_counter_bits_11_0])

    @test_counter.setter
    def test_counter(self, value):
        allbits = bah.fromuint(value, 16)
        self.bits[self.test_counter_bits_15_12] = (
            bah.fromuint(allbits[:4], self.test_counter_bits_15_12))
        self.bits[self.test_counter_bits_11_0] = (
            bah.fromuint(allbits[4:], self.test_counter_bits_11_0))
