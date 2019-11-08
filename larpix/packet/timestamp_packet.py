from bitarray import bitarray
import struct

from .. import bitarrayhelper as bah
from ..key import Key

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
        return struct.pack('Q', self.timestamp)
