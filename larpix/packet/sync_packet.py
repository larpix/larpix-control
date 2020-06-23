from collections import defaultdict

from larpix import Key

class SyncPacket(object):
    '''
    A packet-like object which contains "sync" data (e.g. associated with
    sync words in the PACMAN ZMQ message format).

    It implements the core methods used by Packet, so it works seamlessly in
    lists of packets and in a PacketCollection.

    :param sync_type: optional, an 8-bit type indication for the sync type
    
    :param clk_source: optional, a 1-bit indicator used in clock switch packets

    :param timestamp: optional, a 32-bit timestamp

    :param io_group: optional, an 8-bit io_group id

    '''
    packet_type = 6
    
    pretty_sync_type = defaultdict(lambda:'OTHER')
    pretty_sync_type[b'S'] = 'SYNC'
    pretty_sync_type[b'H'] = 'HEARTBEAT'
    pretty_sync_type[b'C'] = 'CLOCK SWITCH'
    
    def __init__(self, sync_type=None, clk_source=None, timestamp=None, io_group=None):
        self.sync_type = sync_type
        self.clk_source = clk_source
        self.timestamp = timestamp
        self.io_group = io_group

    def __eq__(self, other):
        if self.sync_type != other.sync_type: return False
        if self.clk_source != other.clk_source: return False
        if self.timestamp != other.timestamp: return False
        if self.io_group != other.io_group: return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        strings = ['Sync']
        if self.io_group is not None:
            strings.append('IO group: {}'.format(self.io_group))        
        if self.sync_type is not None:
            strings.append('Type: {}'.format(self.pretty_sync_type[self.sync_type]))
        if self.timestamp is not None:
            strings.append('Timestamp: {}'.format(self.timestamp))
        if self.clk_source is not None:
            strings.append('Clk source: {}'.format(self.clk_source))
        return '[ '+' | '.join(strings)+' ]'

    def __repr__(self):
        strings = list()
        if self.io_group is not None:
            strings.append('io_group={}'.format(self.io_group))        
        if self.sync_type is not None:
            strings.append('sync_type={}'.format(self.sync_type))
        if self.timestamp is not None:
            strings.append('timestamp={}'.format(self.timestamp))
        if self.clk_source is not None:
            strings.append('clk_source={}'.format(self.clk_source))
        return 'SyncPacket('+', '.join(strings)+')'

    def export(self):
        d = dict()
        d['io_group'] = self.io_group
        d['sync_type'] = self.sync_type
        d['timestamp'] = self.timestamp
        d['clk_source'] = self.clk_source
        d['type'] = self.packet_type
        return d

    def from_dict(self, d):
        if 'io_group' in d:
            self.io_group = d['io_group']
        if 'sync_type' in d:
            self.sync_type = d['sync_type']
        if 'timestamp' in d:
            self.timestamp = d['timestamp']
        if 'clk_source' in d:
            self.clk_source = d['clk_source']

    @property
    def chip_key(self):
        if self.io_group:
            return Key(self.io_group,0,0)
        return None

    @chip_key.setter
    def chip_key(self, val):
        key = Key(val)
        self.io_group = key.io_group
