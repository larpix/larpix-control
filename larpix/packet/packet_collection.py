from bitarray import bitarray
import struct

from .. import bitarrayhelper as bah
from ..key import Key
from . import Packet

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

    def extract(self, *attrs, **selection):
        '''
        Extract the given attribute(s) from packets specified by selection
        and return a list.

        Any attribute of a Packet is a valid attribute or selection

        Usage:

        >>> # Return a list of adc counts from any data packets
        >>> dataword = collection.extract('dataword', packet_type=0)
        >>> # Return a list of timestamps from chip 2 data
        >>> timestamps = collection.extract('timestamp', chip_id=2, packet_type=Packet_v2.DATA_PACKET)
        >>> # Return the most recently read global threshold from chip 5
        >>> threshold = collection.extract('register_value', register_address=32, packet_type=3, chip_id=5)[-1]
        >>> # Return multiple attributes
        >>> chip_keys, channel_ids = zip(*collection.extract('chip_key','channel_id'))

        .. note:: selecting on ``timestamp`` will also select
            TimestampPacket values.
        '''
        values = []
        for p in self.packets:
            try:
                if all(getattr(p,key) == value for key, value in selection.items()):
                    if len(attrs) > 1:
                        values.append([getattr(p,attr) for attr in attrs])
                    else:
                        values.append(getattr(p,attrs[0]))
            except AttributeError:
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
        Return a dict of { chip_key: PacketCollection }.

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
            to_return[chip_key] = new_collection
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
            chip_groups.setdefault(packet.chip_id, []).append(packet)
        to_return = {}
        for chipid in chip_groups:
            new_collection = PacketCollection(chip_groups[chipid])
            new_collection.message = self.message + ' | chip %s' % chipid
            new_collection.read_id = self.read_id
            new_collection.parent = self
            to_return[chipid] = new_collection
        return to_return
