from bitarray import bitarray
import struct

from . import bitarrayhelper as bah
from .key import Key

class TimestampPacket(object):
    '''
    A packet-like object which just contains an integer timestamp.

    This class implements many methods used by Packet, so it functions
    smoothly in lists of packets and in PacketCollection.

    If neither ``timestamp`` nor ``code`` is provided then this
    TimestampPacket will have a timestamp of ``None`` until it is
    manually set.

    :param timestamp: optional, integer timestamp of this packet
    :param code: optional, encoded timestamp as a 7-byte unsigned int
        obtainable from calling the ``bytes`` method.

    '''
    size = 56
    chip_key = None
    def __init__(self, timestamp=None, code=None):
        self.packet_type = 4
        if code:
            self.timestamp = struct.unpack('<Q', code + b'\x00')[0]
        else:
            self.timestamp = timestamp

    def __str__(self):
        return '[ Timestamp: %d ]' % self.timestamp

    def __repr__(self):
        return 'TimestampPacket(%d)' % self.timestamp

    def __eq__(self, other):
        return self.timestamp == other.timestamp

    def __ne__(self, other):
        return not (self == other)

    def export(self):
        return {
                'type_str': 'timestamp',
                'type': self.packet_type,
                'timestamp': self.timestamp,
                'bits': self.bits.to01(),
                }

    def from_dict(self, d):
        ''' Inverse of export - modify packet based on dict '''
        if 'type' in d and d['type'] != self.packet_type:
            raise ValueError('invalid packet type for TimestampPacket')
        for key, value in d.items():
            if key == 'type':
                self.packet_type = value
            elif key == 'type_str':
                continue
            elif key == 'bits':
                self.bits = bitarray(value)
            else:
                setattr(self, key, value)

    @property
    def bits(self):
        return bah.fromuint(self.timestamp, self.size)

    @bits.setter
    def bits(self, value):
        self.timestamp = bah.touint(value)

    def bytes(self):
        return struct.pack('Q', self.timestamp)[:7]  # length-7

class MessagePacket(object):
    '''
    A packet-like object which contains a string message and timestamp.

    :param message: a string message of length less than 64
    :param timestamp: the timestamp of the message

    '''
    size=72
    chip_key = None
    def __init__(self, message, timestamp):
        self.packet_type = 5
        self.message = message
        self.timestamp = timestamp

    def __str__(self):
        return '[ Message: %s | Timestamp: %d ]' % (self.message,
                self.timestamp)

    def __repr__(self):
        return 'MessagePacket(%s, %d)' % (repr(self.message),
                self.timestamp)

    def __eq__(self, other):
        return (self.message == other.message
                and self.timestamp == other.timestamp)

    def __ne__(self, other):
        return not (self == other)

    def export(self):
        return {
                'type_str': 'message',
                'type': self.packet_type,
                'message': self.message,
                'timestamp': self.timestamp,
                'bits': self.bits.to01(),
                }

    def from_dict(self, d):
        ''' Inverse of export - modify packet based on dict '''
        if 'type' in d and d['type'] != self.packet_type:
            raise ValueError('invalid packet type for MessagePacket')
        for key, value in d.items():
            if key == 'type':
                self.packet_type = value
            elif key == 'type_str':
                continue
            elif key == 'bits':
                self.bits = bitarray(value)
            else:
                setattr(self, key, value)

    @property
    def bits(self):
        b = bitarray()
        b.frombytes(self.bytes())
        return b

    @bits.setter
    def bits(self, value):
        value_bytes = value.tobytes()
        message_bytes = value_bytes[:64]
        timestamp_bytes = value_bytes[64:]
        self.message = message_bytes[:message_bytes.find(b'\x00')].decode()
        self.timestamp = struct.unpack('Q', timestamp_bytes)[0]

    def bytes(self):
        return (self.message.ljust(64, '\x00').encode()
                + struct.pack('Q', self.timestamp))


class Packet(object):
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
            self.bits = bitarray(Packet.size)
            self.bits.setall(False)
            return
        elif len(bytestream) == Packet.num_bytes:
            # Parse the bytestream. Remember that bytestream[0] goes at
            # the 'end' of the BitArray
            reversed_bytestream = bytestream[::-1]
            self.bits = bitarray()
            self.bits.frombytes(reversed_bytestream)
            # Get rid of the padding (now at the beginning of the
            # bitstream because of the reverse order)
            self.bits.pop(0)
            self.bits.pop(0)
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
            string += {Logger.WRITE: 'Out', Logger.READ: 'In'}[self.direction]
            string += ' | '
        ptype = self.packet_type
        if ptype == Packet.TEST_PACKET:
            string += 'Test | '
            string += 'Counter: %d | ' % self.test_counter
        elif ptype == Packet.DATA_PACKET:
            string += 'Data | '
            string += 'Channel: %d | ' % self.channel_id
            string += 'Timestamp: %d | ' % self.timestamp
            string += 'ADC data: %d | ' % self.dataword
            string += 'FIFO Half: %s | ' % bool(self.fifo_half_flag)
            string += 'FIFO Full: %s | ' % bool(self.fifo_full_flag)
        elif (ptype == Packet.CONFIG_READ_PACKET or ptype ==
                Packet.CONFIG_WRITE_PACKET):
            if ptype == Packet.CONFIG_READ_PACKET:
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
        return 'Packet(' + str(self.bytes()) + ')'

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
        d['chip_key'] = str(self.chip_key) if self.chip_key else None
        d['bits'] = self.bits.to01()
        d['type_str'] = type_map[self.packet_type.to01()]
        d['type'] = bah.touint(self.packet_type)
        d['chipid'] = self.chipid
        d['parity'] = self.parity_bit_value
        d['valid_parity'] = self.has_valid_parity()
        ptype = self.packet_type
        if ptype == Packet.TEST_PACKET:
            d['counter'] = self.test_counter
        elif ptype == Packet.DATA_PACKET:
            d['channel'] = self.channel_id
            d['timestamp'] = self.timestamp
            d['adc_counts'] = self.dataword
            d['fifo_half'] = bool(self.fifo_half_flag)
            d['fifo_full'] = bool(self.fifo_full_flag)
        elif (ptype == Packet.CONFIG_READ_PACKET or ptype ==
                Packet.CONFIG_WRITE_PACKET):
            d['register'] = self.register_address
            d['value'] = self.register_data
        return d

    def from_dict(self, d):
        ''' Inverse of export - modify packet based on dict '''
        if 'type' in d and d['type'] not in [bah.touint(packet_type) for packet_type in \
            (Packet.DATA_PACKET, Packet.TEST_PACKET, Packet.CONFIG_WRITE_PACKET, Packet.CONFIG_READ_PACKET)]:
            raise ValueError('invalid packet type for Packet')
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
        try:
            return self._chip_key
        except AttributeError:
            return None

    @chip_key.setter
    def chip_key(self, value):
        if value is None:
            if self.chip_key is None:
                return
            delattr(self, '_chip_key')
            return
        if isinstance(value, Key):
            self._chip_key = value
        self._chip_key = Key(value)
        self.chipid = self._chip_key.chip_id

    @property
    def packet_type(self):
        return self.bits[Packet.packet_type_bits]

    @packet_type.setter
    def packet_type(self, value):
        self.bits[Packet.packet_type_bits] = bah.fromuint(value,
                Packet.packet_type_bits)

    @property
    def chipid(self):
        return bah.touint(self.bits[Packet.chipid_bits])

    @chipid.setter
    def chipid(self, value):
        if not self.chip_key is None:
            self.chip_key.chip_id = value
        self.bits[Packet.chipid_bits] = bah.fromuint(value,
                Packet.chipid_bits)

    @property
    def parity_bit_value(self):
        return int(self.bits[Packet.parity_bit])

    @parity_bit_value.setter
    def parity_bit_value(self, value):
        self.bits[Packet.parity_bit] = bool(value)

    def compute_parity(self):
        return 1 - (self.bits[Packet.parity_calc_bits].count(True) % 2)

    def assign_parity(self):
        self.parity_bit_value = self.compute_parity()

    def has_valid_parity(self):
        return self.parity_bit_value == self.compute_parity()

    @property
    def channel_id(self):
        return bah.touint(self.bits[Packet.channel_id_bits])

    @channel_id.setter
    def channel_id(self, value):
        self.bits[Packet.channel_id_bits] = bah.fromuint(value,
                Packet.channel_id_bits)

    @property
    def timestamp(self):
        return bah.touint(self.bits[Packet.timestamp_bits])

    @timestamp.setter
    def timestamp(self, value):
        self.bits[Packet.timestamp_bits] = bah.fromuint(value,
                Packet.timestamp_bits)

    @property
    def dataword(self):
        ostensible_value = bah.touint(self.bits[Packet.dataword_bits])
        # TODO fix in LArPix v2
        return ostensible_value - (ostensible_value % 2)

    @dataword.setter
    def dataword(self, value):
        self.bits[Packet.dataword_bits] = bah.fromuint(value,
                Packet.dataword_bits)

    @property
    def fifo_half_flag(self):
        return int(self.bits[Packet.fifo_half_bit])

    @fifo_half_flag.setter
    def fifo_half_flag(self, value):
        self.bits[Packet.fifo_half_bit] = bool(value)

    @property
    def fifo_full_flag(self):
        return int(self.bits[Packet.fifo_full_bit])

    @fifo_full_flag.setter
    def fifo_full_flag(self, value):
        self.bits[Packet.fifo_full_bit] = bool(value)

    @property
    def register_address(self):
        return bah.touint(self.bits[Packet.register_address_bits])

    @register_address.setter
    def register_address(self, value):
        self.bits[Packet.register_address_bits] = bah.fromuint(value,
                Packet.register_address_bits)

    @property
    def register_data(self):
        return bah.touint(self.bits[Packet.register_data_bits])

    @register_data.setter
    def register_data(self, value):
        self.bits[Packet.register_data_bits] = bah.fromuint(value,
                Packet.register_data_bits)

    @property
    def test_counter(self):
        return bah.touint(self.bits[Packet.test_counter_bits_15_12] +
                self.bits[Packet.test_counter_bits_11_0])

    @test_counter.setter
    def test_counter(self, value):
        allbits = bah.fromuint(value, 16)
        self.bits[Packet.test_counter_bits_15_12] = (
            bah.fromuint(allbits[:4], Packet.test_counter_bits_15_12))
        self.bits[Packet.test_counter_bits_11_0] = (
            bah.fromuint(allbits[4:], Packet.test_counter_bits_11_0))

class PacketCollection(object):
    '''
    Represents a group of packets that were sent to or received from
    LArPix.

    Index into the PacketCollection as if it were a list:

        >>> collection[0]
        Packet(b'\x07\x00\x00\x00\x00\x00\x00')
        >>> first_ten = collection[:10]
        >>> len(first_ten)
        10
        >>> type(first_ten)
        larpix.larpix.PacketCollection
        >>> first_ten.message
        'my packets | subset slice(None, 10, None)'

    To view the bits representation, add 'bits' to the index:

        >>> collection[0, 'bits']
        '00000000 00000000 00000000 00000000 00000000 00000000 000111'
        >>> bits_format_first_10 = collection[:10, 'bits']
        >>> type(bits_format_first_10[0])
        str


    '''
    def __init__(self, packets, bytestream=None, message='',
            read_id=None, skipped=None):
        self.packets = packets
        self.bytestream = bytestream
        self.skipped = skipped
        self.message = message
        self.read_id = read_id
        self.parent = None

    def __eq__(self, other):
        '''
        Return True if the packets, message and bytestream compare equal.

        '''
        return (self.packets == other.packets and
                self.message == other.message and
                self.bytestream == other.bytestream)

    def __repr__(self):
        return '<%s with %d packets, read_id %d, "%s">' % (self.__class__.__name__,
                len(self.packets), self.read_id, self.message)

    def __str__(self):
        if len(self.packets) < 20:
            return '\n'.join(str(packet) for packet in self.packets)
        else:
            beginning = '\n'.join(str(packet) for packet in self.packets[:10])
            middle = '\n'.join(['   .', '   . omitted %d packets' %
                (len(self.packets)-20), '   .'])
            end = '\n'.join(str(packet) for packet in self.packets[-10:])
            return '\n'.join([beginning, middle, end])

    def __len__(self):
        return len(self.packets)

    def __getitem__(self, key):
        '''
        Get the specified item(s).

        If key is an int, return the packet object at that index in
        self.packets.

        If key is a slice, return a PacketCollection with the specified
        packets, and with a message inherited from self.message.

        If key is (slice or int, 'str'), use the behavior as if setting
        key = key[0].

        If key is (int, 'bits'), return a string representation of the
        bits of the specified packet, as determined by
        self._bits_getitem.

        If key is (slice, 'bits'), return a list of string
        representations of the packets specified by the slice.

        '''
        if isinstance(key, slice):
            items = PacketCollection([p for p in self.packets[key]])
            items.message = '%s | subset %s' % (self.message, key)
            items.parent = self
            items.read_id = self.read_id
            return items
        elif isinstance(key, tuple):
            if key[1] == 'bits':
                return self._bits_getitem(key[0])
            elif key[1] == 'str':
                return self[key[0]]
        else:
            return self.packets[key]

    def _bits_getitem(self, key):
        '''
        Replace each packet with a string of the packet bits grouped 8
        bits at a time.

        '''
        if isinstance(key, slice):
            return [' '.join(p.bits.to01()[i:i+8] for i in
                range(0, p.size, 8)) for p in self.packets[key]]
        else:
            p = self.packets[key]
            return ' '.join(p.bits.to01()[i:i+8] for i in
                    range(0, p.size, 8))

    def to_dict(self):
        '''
        Export the information in this PacketCollection to a dict.

        '''
        d = {}
        d['packets'] = [packet.export() for packet in self.packets]
        d['id'] = id(self)
        d['parent'] = 'None' if self.parent is None else id(self.parent)
        d['message'] = str(self.message)
        d['read_id'] = 'None' if self.read_id is None else self.read_id
        d['bytestream'] = ('None' if self.bytestream is None else
                self.bytestream.decode('raw_unicode_escape'))
        return d

    def from_dict(self, d):
        '''
        Load the information in the dict into this PacketCollection.

        '''
        self.message = d['message']
        self.read_id = d['read_id']
        self.bytestream = d['bytestream'].encode('raw_unicode_escape')
        self.parent = None
        self.packets = []
        for p in d['packets']:
            bits = p['bits']
            packet = Packet()
            packet.bits = bitarray(bits)
            self.packets.append(packet)

    def extract(self, attr, **selection):
        '''
        Extract the given attribute from packets specified by selection
        and return a list.

        Any key used in Packet.export is a valid attribute or selection:

        - all packets:
             - chip_key
             - bits
             - type_str (data, test, config read, config write)
             - type (0, 1, 2, 3)
             - chipid
             - parity
             - valid_parity
        - data packets:
             - channel
             - timestamp
             - adc_counts
             - fifo_half
             - fifo_full
        - test packets:
             - counter
        - config packets:
             - register
             - value

        Usage:

        >>> # Return a list of adc counts from any data packets
        >>> adc_data = collection.extract('adc_counts')
        >>> # Return a list of timestamps from chip 2 data
        >>> timestamps = collection.extract('timestamp', chipid=2)
        >>> # Return the most recently read global threshold from chip 5
        >>> threshold = collection.extract('value', register=32, type='config read', chip=5)[-1]

        .. note:: selecting on ``timestamp`` will also select
            TimestampPacket values.
        '''
        values = []
        for p in self.packets:
            try:
                d = p.export()
                if all( d[key] == value for key, value in selection.items()):
                    values.append(d[attr])
            except KeyError:
                continue
        return values

    def origin(self):
        '''
        Return the original PacketCollection that this PacketCollection
        derives from.

        '''
        child = self
        parent = self.parent
        max_generations = 100  # to prevent infinite loops
        i = 0
        while parent is not None and i < max_generations:
            # Move up the family tree one generation
            child = parent
            parent = parent.parent
            i += 1
        if parent is None:
            return child
        else:
            raise ValueError('Reached limit on generations: %d' %
                    max_generations)

    def with_chip_key(self, chip_key):
        '''
        Return packets with the specified chip key.

        '''
        return [packet for packet in self.packets \
            if packet.chip_key == chip_key]

    def by_chip_key(self):
        '''
        Return a dict of { chipid: PacketCollection }.

        '''
        chip_groups = {}
        for packet in self.packets:
            # append packet to list if list exists, else append to empty
            # list as a default
            key = packet.chip_key
            chip_groups.setdefault(key, []).append(packet)
        to_return = {}
        for chip_key in chip_groups:
            new_collection = PacketCollection(chip_groups[chip_key])
            new_collection.message = self.message + ' | chip {}'.format(chip_key)
            new_collection.read_id = self.read_id
            new_collection.parent = self
            to_return[chipid] = new_collection
        return to_return

    def with_chipid(self, chipid):
        '''
        Return packets with the specified chip ID.

        '''
        return [packet for packet in self.packets if packet.chipid == chipid]

    def by_chipid(self):
        '''
        Return a dict of { chipid: PacketCollection }.

        '''
        chip_groups = {}
        for packet in self.packets:
            # append packet to list if list exists, else append to empty
            # list as a default
            chip_groups.setdefault(packet.chipid, []).append(packet)
        to_return = {}
        for chipid in chip_groups:
            new_collection = PacketCollection(chip_groups[chipid])
            new_collection.message = self.message + ' | chip %s' % chipid
            new_collection.read_id = self.read_id
            new_collection.parent = self
            to_return[chipid] = new_collection
        return to_return

