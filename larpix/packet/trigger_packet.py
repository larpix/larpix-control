
from larpix import Key

class TriggerPacket(object):
    '''
    A packet-like object which contains trigger data (e.g. associated with
    trigger words in the PACMAN ZMQ message format).

    It implements the core methods used by Packet, so it works seamlessly in
    lists of packets and in a PacketCollection.

    :param trigger_type: optional, an 8-bit type indication for the trigger type
    
    :param timestamp: optional, a 32-bit timestamp

    :param io_group: optional, an 8-bit io_group id

    '''
    packet_type = 7
    
    def __init__(self, trigger_type=None, timestamp=None, io_group=None):
        self.trigger_type = trigger_type
        self.timestamp = timestamp
        self.io_group = io_group

    def __eq__(self, other):
        if self.trigger_type != other.trigger_type: return False
        if self.timestamp != other.timestamp: return False
        if self.io_group != other.io_group: return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        strings = ['Trigger']
        if self.io_group is not None:
            strings.append('IO group: {}'.format(self.io_group))        
        if self.trigger_type is not None:
            strings.append('Type: {}'.format(self.trigger_type))
        if self.timestamp is not None:
            strings.append('Timestamp: {}'.format(self.timestamp))
        return '[ '+' | '.join(strings)+' ]'

    def __repr__(self):
        strings = list()
        if self.io_group is not None:
            strings.append('io_group={}'.format(self.io_group))        
        if self.trigger_type is not None:
            strings.append('trigger_type={}'.format(self.trigger_type))
        if self.timestamp is not None:
            strings.append('timestamp={}'.format(self.timestamp))
        return 'TriggerPacket('+', '.join(strings)+')'

    def export(self):
        d = dict()
        d['io_group'] = self.io_group
        d['trigger_type'] = self.trigger_type
        d['timestamp'] = self.timestamp
        d['type'] = self.packet_type
        return d

    def from_dict(self, d):
        if 'io_group' in d:
            self.io_group = d['io_group']
        if 'trigger_type' in d:
            self.trigger_type = d['trigger_type']
        if 'timestamp' in d:
            self.timestamp = d['timestamp']

    @property
    def chip_key(self):
        if self.io_group:
            return Key(self.io_group,0,0)
        return None

    @chip_key.setter
    def	chip_key(self, val):
        key = Key(val)
        self.io_group = key.io_group
