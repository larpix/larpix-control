from bitarray import bitarray

from .. import bitarrayhelper as bah
from ..key import Key

class Packet_v2(object):
    '''
    Representation of a 64 bit LArPix v2 UART data packet.

    Packet_v2 objects are internally represented as bitarrays, but a variety of
    helper properties allow one to access and set the data stored in the bitarrays in
    a natural fashion. E.g.::

        p = Packet_v2() # initialize a packet of zeros
        p.packet_type # fetch packet type bits and convert to uint
        p.packet_type = 2 # set the packet type to a config write packet
        print(p.bits) # the bits have been updated!

    Packet_v2 objects don't enforce any value validation, so set these fields with caution!

    In FIFO diagnostics mode, the bits are to be interpreted in a different way.
    At this point, there is no way for the ``Packet_v2`` to automatically know if it
    is in FIFO diagnostics mode. If you are operating the chips in this mode you
    can manually set ``Packet_v2.fifo_diagnostics_enabled = True`` to interpret
    data packets in this fashion by default, or set ``packet.fifo_diagnostics_enabled = True``
    for a single packet. Just remember that if you modify ``packet.fifo_diagnostics_enabled``,
    it will no longer use the default.

    '''

    asic_version = 2
    size = 64
    num_bytes = 8

    # shared by all packet types
    packet_type_bits = slice(0,2)
    chip_id_bits = slice(2,10)
    downstream_marker_bits = slice(62,63)
    parity_bits = slice(63,64)
    parity_calc_bits = slice(0,63)

    # only data packets
    channel_id_bits = slice(10,16)
    timestamp_bits = slice(16,48)
    dataword_bits = slice(48,56)
    trigger_type_bits = slice(56,58)
    local_fifo_bits = slice(58,60)
    shared_fifo_bits = slice(60,62)
    # only if fifo diagnostics enabled
    fifo_diagnostics_timestamp_bits = slice(16,32)
    local_fifo_events_bits = slice(44,46)
    shared_fifo_events_bits = slice(32,44)

    # only read/write packets
    register_address_bits = slice(10,18)
    register_data_bits = slice(18,26)

    fifo_diagnostics_enabled = False

    DATA_PACKET = 0
    TEST_PACKET = 1
    CONFIG_WRITE_PACKET = 2
    CONFIG_READ_PACKET = 3

    NORMAL_TRIG = 0
    EXT_TRIG = 1
    CROSS_TRIG = 2
    PERIODIC_TRIG = 3

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
        else:
            raise ValueError('Invalid number of bytes: %s' %
                    len(bytestream))

    def __eq__(self, other):
        return self.bits == other.bits

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        strings = []
        if hasattr(self, 'direction'):
            strings += ['Direction: {}'.format(self.direction)]
        strings += ['Key: {}'.format(self.chip_key)]
        strings += ['Chip: {}'.format(self.chip_id)]
        if self.downstream_marker:
            strings += ['Downstream']
        else:
            strings += ['Upstream']
        if self.packet_type == self.DATA_PACKET:
            strings += ['Data']
            strings += ['Channel: {}'.format(self.channel_id)]
            strings += ['Timstamp: {}'.format(self.timestamp)]
            strings += ['Dataword: {}'.format(self.dataword)]
            strings += ['Trigger: {}'.format({
                self.NORMAL_TRIG: 'normal',
                self.EXT_TRIG: 'external',
                self.CROSS_TRIG: 'cross',
                self.PERIODIC_TRIG: 'periodic'
                }[self.trigger_type])]
            if self.local_fifo_full:
                strings += ['Local FIFO 100%']
            elif self.local_fifo_half:
                strings += ['Local FIFO >50%']
            else:
                strings += ['Local FIFO ok']
            if self.shared_fifo_full:
                strings += ['Shared FIFO 100%']
            elif self.shared_fifo_half:
                strings += ['Shared FIFO >50%']
            else:
                strings += ['Shared FIFO ok']
            if self.fifo_diagnostics_enabled:
                strings += ['Local FIFO: {}'.format(self.local_fifo_events)]
                strings += ['Shared FIFO: {}'.format(self.shared_fifo_events)]
        elif self.packet_type == self.TEST_PACKET:
            strings += ['Test']
        elif self.packet_type in (self.CONFIG_READ_PACKET, self.CONFIG_WRITE_PACKET):
            strings += [{
                self.CONFIG_READ_PACKET: 'Read',
                self.CONFIG_WRITE_PACKET: 'Write'
            }[self.packet_type]]
            strings += ['Register: {}'.format(self.register_address)]
            strings += ['Value: {}'.format(self.register_data)]

        strings += ['Parity: {} (valid: {})'.format(self.parity,
            self.has_valid_parity())]
        return '[ ' + ' | '.join(strings) + ' ]'

    def __repr__(self):
        return 'Packet_v2(' + str(self.bytes()) + ')'

    def bytes(self):
        '''
        Create bytes that represent the packet.

        Byte 0 is still the first byte to send out and contains bits [0:7]

        '''
        return self.bits.tobytes()[::-1]

    def export(self):
        '''
        Return a dict representation of the packet

        '''
        type_map = {
                self.TEST_PACKET: 'test',
                self.DATA_PACKET: 'data',
                self.CONFIG_WRITE_PACKET: 'config write',
                self.CONFIG_READ_PACKET: 'config read'
                }
        d = {}
        d['asic_version'] = self.asic_version
        d['chip_key'] = str(self.chip_key) if self.chip_key else None
        d['io_group'] = self.io_group
        d['io_channel'] = self.io_channel
        d['bits'] = self.bits.to01()
        d['type_str'] = type_map[self.packet_type]
        d['packet_type'] = self.packet_type
        d['chip_id'] = self.chip_id
        d['downstream_marker'] = self.downstream_marker
        d['parity'] = self.parity
        d['valid_parity'] = self.has_valid_parity()
        ptype = self.packet_type
        if ptype == self.TEST_PACKET:
            pass
        elif ptype == self.DATA_PACKET:
            d['channel_id'] = self.channel_id
            d['timestamp'] = self.timestamp
            d['dataword'] = self.dataword
            d['trigger_type'] = self.trigger_type
            d['local_fifo'] = self.local_fifo
            d['shared_fifo'] = self.shared_fifo
            if self.fifo_diagnostics_enabled:
                d['local_fifo_events'] = self.local_fifo_events
                d['shared_fifo_events'] = self.shared_fifo_events
        elif (ptype == self.CONFIG_READ_PACKET or ptype ==
                self.CONFIG_WRITE_PACKET):
            d['register_address'] = self.register_address
            d['register_data'] = self.register_data
        if hasattr(self,'direction'):
            d['direction'] = self.direction
        return d

    def from_dict(self, d):
        '''
        Load from a dict of values, inverse of ``Packet_v2.export``

        .. note:: If there is a disagreement between the bits specified and any of the values, this method has undefined results.

        '''
        if not d['asic_version'] == self.asic_version:
            raise ValueError('invalid asic version {}'.format(d['asic_version']))
        if 'type' in d and d['type'] not in (self.DATA_PACKET, self.TEST_PACKET, self.CONFIG_WRITE_PACKET, self.CONFIG_READ_PACKET):
            raise ValueError('invalid packet type for Packet_v2')
        if 'local_fifo_events' in d or 'shared_fifo_events' in d:
            self.fifo_diagnostics_enabled = True
        for key, value in d.items():
            if key in ('type_str', 'valid_parity'):
                continue
            elif key == 'bits':
                self.bits = bitarray(value)
            else:
                setattr(self, key, value)
            print(key, self.bits)

    @property
    def chip_key(self):
        ''''''
        if hasattr(self, '_chip_key'):
            return self._chip_key
        if self.io_group is None or self.io_channel is None:
            return None
        self._chip_key = Key(self.io_group, self.io_channel, self.chip_id)
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
            self.chip_id = value.chip_id
            return
        # try again by casting as a Key
        self.chip_key = Key(value)

    @property
    def io_group(self):
        ''''''
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
    def timestamp(self):
        if self.fifo_diagnostics_enabled:
            return bah.touint(self.bits[self.fifo_diagnostics_timestamp_bits])
        return bah.touint(self.bits[self.timestamp_bits])

    @timestamp.setter
    def timestamp(self, value):
        if self.fifo_diagnostics_enabled:
            self.bits[self.fifo_diagnostics_timestamp_bits] = bah.fromuint(value, self.fifo_diagnostics_timestamp_bits)
        else:
            self.bits[self.timestamp_bits] = bah.fromuint(value, self.timestamp_bits)

    @property
    def local_fifo_half(self):
        return self.local_fifo%2

    @local_fifo_half.setter
    def local_fifo_half(self, value):
        self.local_fifo = self.local_fifo_full*2 + value

    @property
    def local_fifo_full(self):
        return self.local_fifo//2

    @local_fifo_full.setter
    def local_fifo_full(self, value):
        self.local_fifo = value*2 + self.local_fifo_half

    @property
    def shared_fifo_half(self):
        return self.shared_fifo%2

    @shared_fifo_half.setter
    def shared_fifo_half(self, value):
        self.shared_fifo = self.shared_fifo_full*2 + value

    @property
    def shared_fifo_full(self):
        return self.shared_fifo//2

    @shared_fifo_full.setter
    def shared_fifo_full(self, value):
        self.shared_fifo = value*2 + self.shared_fifo_half

    def compute_parity(self):
        return 1 - (self.bits[self.parity_calc_bits].count(True) % 2)

    def assign_parity(self):
        self.parity = self.compute_parity()

    def has_valid_parity(self):
        return self.parity == self.compute_parity()

    @property
    def local_fifo_events(self):
        if self.fifo_diagnostics_enabled:
            bit_slice = self.local_fifo_events_bits
            return bah.touint(self.bits[bit_slice])
        return None

    @local_fifo_events.setter
    def local_fifo_events(self, value):
        if self.fifo_diagnostics_enabled:
            bit_slice = self.local_fifo_events_bits
            self.bits[bit_slice] = bah.fromuint(value, bit_slice)

    @property
    def shared_fifo_events(self):
        if self.fifo_diagnostics_enabled:
            bit_slice = self.shared_fifo_events_bits
            return bah.touint(self.bits[bit_slice])
        return None

    @shared_fifo_events.setter
    def shared_fifo_events(self, value):
        if self.fifo_diagnostics_enabled:
            bit_slice = self.shared_fifo_events_bits
            self.bits[bit_slice] = bah.fromuint(value, bit_slice)

    @property
    def chip_id(self):
        bit_slice = self.chip_id_bits
        return bah.touint(self.bits[bit_slice])

    @chip_id.setter
    def chip_id(self, value):
        if hasattr(self,'_chip_key'):
            del self._chip_key
        bit_slice = self.chip_id_bits
        self.bits[bit_slice] = bah.fromuint(value, bit_slice)

    def _basic_getter(name):
        def basic_getter_func(self):
            bit_slice = getattr(self, name + '_bits')
            return bah.touint(self.bits[bit_slice])
        return basic_getter_func

    def _basic_setter(name):
        def basic_setter_func(self, value):
            bit_slice = getattr(self, name + '_bits')
            self.bits[bit_slice] = bah.fromuint(value, bit_slice)
        return basic_setter_func

    packet_type = property(_basic_getter('packet_type'),_basic_setter('packet_type'))
    downstream_marker = property(_basic_getter('downstream_marker'),_basic_setter('downstream_marker'))
    parity = property(_basic_getter('parity'),_basic_setter('parity'))
    channel_id = property(_basic_getter('channel_id'),_basic_setter('channel_id'))
    dataword = property(_basic_getter('dataword'),_basic_setter('dataword'))
    trigger_type = property(_basic_getter('trigger_type'),_basic_setter('trigger_type'))
    register_address = property(_basic_getter('register_address'),_basic_setter('register_address'))
    register_data = property(_basic_getter('register_data'),_basic_setter('register_data'))
    local_fifo = property(_basic_getter('local_fifo'),_basic_setter('local_fifo'))
    shared_fifo = property(_basic_getter('shared_fifo'),_basic_setter('shared_fifo'))
