from bitarray import bitarray
import struct

from .. import bitarrayhelper as bah
from ..key import Key

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

