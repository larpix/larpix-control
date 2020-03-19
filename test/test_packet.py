from bitarray import bitarray
import copy

from larpix import Packet_v2
from larpix import bitarrayhelper as bah

packet_types = {
    'data':Packet_v2.DATA_PACKET,
    'test':Packet_v2.TEST_PACKET,
    'write':Packet_v2.CONFIG_WRITE_PACKET,
    'read':Packet_v2.CONFIG_READ_PACKET
    }
shared_fields = ['chip_id','downstream_marker','parity']
data_fields = ['channel_id','timestamp','dataword','trigger_type','local_fifo','shared_fifo']
write_read_fields = ['register_address','register_data']

def test_basic():
    p1 = Packet_v2()
    assert p1.bits == bitarray('0'*64)
    assert p1 == Packet_v2()
    assert p1.bytes() == b'\x00'*8

    p2 = Packet_v2(b'\x01' + b'\x00'*7)
    assert p2 != p1
    assert p2.bits == bitarray('10000000') + bitarray('0'*56)

def test_field_assignment():
    '''
    Tests that you can properly get, set, export, and from_dict each simple data
    attribute

    '''

    p = Packet_v2()

    def test_field(packet, field_name):
        print('testing {}'.format(field_name))
        p = copy.deepcopy(packet)

        assert getattr(p,field_name) == 0
        assert bah.touint(p.bits[getattr(p,field_name+'_bits')], endian=p.endian) == 0

        setattr(p,field_name,1)
        assert getattr(p,field_name) == 1
        assert bah.touint(p.bits[getattr(p,field_name+'_bits')], endian=p.endian) == 1
        assert str(p) # just to make sure there are no errors in printing the string

        p_dict = p.export()
        print(p_dict)
        assert field_name in p_dict
        assert p_dict[field_name] == 1

        p_dict[field_name] = 0
        p2 = Packet_v2(p.bytes())
        setattr(p2, field_name, 0)
        p_dict['bits'] = p2.bits.to01()
        p.from_dict(p_dict)
        assert getattr(p,field_name) == 0
        assert bah.touint(p.bits[getattr(p,field_name+'_bits')], endian=p.endian) == 0


    for type_name, packet_type in packet_types.items():
        print('testing packet type {}'.format(type_name))
        p.packet_type = packet_type
        for field in shared_fields:
            test_field(p, field)
        if type_name == 'data':
            for field in data_fields:
                test_field(p, field)
        elif type_name == 'write':
            for field in write_read_fields:
                test_field(p, field)
        elif type_name == 'read':
            for field in write_read_fields:
                test_field(p, field)

def test_chip_key():
    p = Packet_v2()

    def assert_chip_key(packet, key, group, channel, chip_id):
        assert packet.chip_key == key
        assert packet.io_group == group
        assert packet.io_channel == channel
        assert packet.chip_id == chip_id
        assert bah.touint(p.bits[p.chip_id_bits], endian=p.endian) == chip_id

    # check default values
    assert_chip_key(p,None,None,None,0)

    # check chip key assignment
    p.chip_key = '1-2-3'
    assert_chip_key(p,'1-2-3',1,2,3)

    # check io group assignment
    p.io_group = 4
    assert_chip_key(p,'4-2-3',4,2,3)

    # check io channel assignment
    p.io_channel = 5
    assert_chip_key(p,'4-5-3',4,5,3)

    # check chip id assignment
    p.chip_id = 6
    assert_chip_key(p,'4-5-6',4,5,6)

def test_fifo_diagnostics():
    p = Packet_v2()

    # no fifo diagnositics => local/shared fifo events do nothing
    assert p.fifo_diagnostics_enabled == False
    p.local_fifo_events = 1
    p.shared_fifo_events = 2
    p_dict = p.export()
    assert 'local_fifo_events' not in p_dict.keys()
    assert 'shared_fifo_events' not in p_dict.keys()
    assert p.local_fifo_events == None
    assert p.shared_fifo_events == None
    assert p.timestamp == 0

    # fifo diagnostics => local/shared fifo modify corresponding bits
    p.fifo_diagnostics_enabled = True
    p.local_fifo_events = 1
    p.shared_fifo_events = 2
    p_dict = p.export()
    assert p_dict['local_fifo_events'] == 1
    assert p_dict['shared_fifo_events'] == 2
    assert p.local_fifo_events == 1
    assert p.shared_fifo_events == 2
    assert p.timestamp == 0

    # no fifo diagnostics => local/shared fifo events do nothing again
    p.fifo_diagnostics_enabled = False
    assert p.timestamp == 268566528
    p.local_fifo_events = 7
    p.shared_fifo_events = 8
    assert p.timestamp == 268566528
    assert p.local_fifo_events == None
    assert p.shared_fifo_events == None

def test_parity():
    p = Packet_v2()
    assert p.parity == 0
    assert p.compute_parity() == 1
    assert not p.has_valid_parity()

    p.assign_parity()
    assert p.has_valid_parity()
    assert p.parity == 1

    p.bits[0] = 1
    assert p.parity == 1
    assert p.compute_parity() == 0
    assert not p.has_valid_parity()

    p.assign_parity()
    assert p.has_valid_parity()
    assert p.parity == 0
