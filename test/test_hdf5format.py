from __future__ import print_function

import pytest
import h5py
import copy

from larpix.larpix import (Packet_v1, Packet_v2, PacketCollection, TimestampPacket,
                           MessagePacket, Key, SyncPacket, TriggerPacket, Chip)
from larpix.format.hdf5format import (to_file, from_file,
        dtype_property_index_lookup)

@pytest.fixture
def tmpfile(tmpdir):
    return str(tmpdir.join('test.h5'))

@pytest.fixture
def data_packet():
    p = Packet_v1()
    p.packet_type = Packet_v1.DATA_PACKET
    p.chipid = 123
    p.channel = 7
    p.timestamp = 123456
    p.dataword = 120
    p.fifo_half_flag = 1
    p.assign_parity()
    p.chip_key = Key('1-2-123')
    p.direction = 1
    return p

@pytest.fixture
def config_read_packet():
    p = Packet_v1()
    p.packet_type = Packet_v1.CONFIG_READ_PACKET
    p.chipid = 123
    p.register_address = 10
    p.register_data = 23
    p.assign_parity()
    p.chip_key = Key('1-2-123')
    p.direction = 1
    return p

@pytest.fixture
def data_packet_v2():
    p = Packet_v2()
    p.packet_type = Packet_v2.DATA_PACKET
    p.chip_id = 123
    p.channel_id = 7
    p.timestamp = 123456
    p.dataword = 120
    p.shared_fifo = 1
    p.assign_parity()
    p.chip_key = Key('1-2-123')
    p.direction = 1
    p.receipt_timestamp = 123456
    return p

@pytest.fixture
def fifo_diagnostics_packet_v2():
    p = Packet_v2()
    p.enable_fifo_diagnostics = True
    p.packet_type = Packet_v2.DATA_PACKET
    p.chip_id = 123
    p.channel_id = 7
    p.timestamp = 123456
    p.dataword = 120
    p.shared_fifo = 1
    p.shared_fifo_events = 5
    p.local_fifo_events = 1
    p.assign_parity()
    p.chip_key = Key('1-2-123')
    p.direction = 1
    return p

@pytest.fixture
def config_read_packet_v2():
    p = Packet_v2()
    p.packet_type = Packet_v2.CONFIG_READ_PACKET
    p.chip_id = 123
    p.register_address = 10
    p.register_data = 23
    p.assign_parity()
    p.chip_key = Key('1-2-123')
    p.direction = 1
    return p

@pytest.fixture
def timestamp_packet():
    p = TimestampPacket(timestamp=12345)
    return p

@pytest.fixture
def message_packet():
    p = MessagePacket('Hello, World!', 1234567)
    return p

@pytest.fixture
def sync_packet():
    p = SyncPacket(io_group=1, sync_type=b'A', timestamp=123456, clk_source=1)
    return p

@pytest.fixture
def trigger_packet():
    p = TriggerPacket(io_group=1, trigger_type=b'0', timestamp=123456)
    return p

@pytest.fixture
def chip():
    c = Chip('1-2-3')
    return c

def test_to_file_v0_0_empty(tmpfile):
    to_file(tmpfile, [], version='0.0')
    f = h5py.File(tmpfile, 'r')
    assert f['_header']
    assert f['_header'].attrs['version']
    assert f['_header'].attrs['created']
    assert f['_header'].attrs['modified']
    assert f['raw_packet']

def test_to_file_v0_0_data_packet(tmpfile, data_packet):
    to_file(tmpfile, [data_packet], version='0.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['raw_packet']) == 1
    row = f['raw_packet'][0]
    props = dtype_property_index_lookup['0.0']['raw_packet']
    new_packet = Packet_v1()
    new_packet.chip_key = row[props['chip_key']]
    new_packet.packet_type = row[props['type']]
    new_packet.chipid = row[props['chipid']]
    new_packet.parity_bit_value = row[props['parity']]
    new_packet.channel = row[props['channel']]
    new_packet.timestamp = row[props['timestamp']]
    new_packet.dataword = row[props['adc_counts']]
    new_packet.fifo_half_flag = row[props['fifo_half']]
    new_packet.fifo_full_flag = row[props['fifo_full']]
    assert new_packet == data_packet

def test_to_file_v0_0_config_read_packet(tmpfile, config_read_packet):
    to_file(tmpfile, [config_read_packet], version='0.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['raw_packet']) == 1
    row = f['raw_packet'][0]
    props = dtype_property_index_lookup['0.0']['raw_packet']
    new_packet = Packet_v1()
    new_packet.chip_key = row[props['chip_key']]
    new_packet.packet_type = row[props['type']]
    new_packet.chipid = row[props['chipid']]
    new_packet.parity_bit_value = row[props['parity']]
    new_packet.register_address = row[props['register']]
    new_packet.register_data = row[props['value']]
    assert new_packet == config_read_packet

def test_to_file_v0_0_timestamp_packet(tmpfile, timestamp_packet):
    to_file(tmpfile, [timestamp_packet], version='0.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['raw_packet']) == 1
    row = f['raw_packet'][0]
    props = dtype_property_index_lookup['0.0']['raw_packet']
    assert row[props['type']] == 4  # packet_type
    new_packet = TimestampPacket()
    new_packet.timestamp = row[props['timestamp']]
    assert new_packet == timestamp_packet

def test_to_file_v0_0_many_packets(tmpfile, data_packet, config_read_packet,
        timestamp_packet):
    to_file(tmpfile, [data_packet, config_read_packet,
        timestamp_packet], version='0.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['raw_packet']) == 3

def test_from_file_v0_0_many_packets(tmpfile, data_packet,
        config_read_packet, timestamp_packet):
    packets = [data_packet, config_read_packet, timestamp_packet]
    to_file(tmpfile, packets, version='0.0')
    new_packets_dict = from_file(tmpfile, version='0.0')
    assert new_packets_dict['created']
    assert new_packets_dict['version']
    assert new_packets_dict['modified']
    new_packets = new_packets_dict['packets']
    assert new_packets[0] == data_packet
    assert new_packets[1] == config_read_packet
    assert new_packets[2] == timestamp_packet

def test_to_file_v1_0_empty(tmpfile):
    to_file(tmpfile, [], version='1.0')
    f = h5py.File(tmpfile, 'r')
    assert f['_header']
    assert f['_header'].attrs['version']
    assert f['_header'].attrs['created']
    assert f['_header'].attrs['modified']
    assert f['packets']

def test_to_file_v1_0_data_packet(tmpfile, data_packet):
    to_file(tmpfile, [data_packet], version='1.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 1
    row = f['packets'][0]
    props = dtype_property_index_lookup['1.0']['packets']
    new_packet = Packet_v1()
    new_packet.chip_key = row[props['chip_key']]
    new_packet.packet_type = row[props['type']]
    new_packet.chipid = row[props['chipid']]
    new_packet.parity_bit_value = row[props['parity']]
    new_packet.channel = row[props['channel']]
    new_packet.timestamp = row[props['timestamp']]
    new_packet.dataword = row[props['adc_counts']]
    new_packet.fifo_half_flag = row[props['fifo_half']]
    new_packet.fifo_full_flag = row[props['fifo_full']]
    new_packet.direction = row[props['direction']]
    assert new_packet == data_packet

def test_to_file_v1_0_config_read_packet(tmpfile, config_read_packet):
    to_file(tmpfile, [config_read_packet], version='1.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 1
    row = f['packets'][0]
    props = dtype_property_index_lookup['1.0']['packets']
    new_packet = Packet_v1()
    new_packet.chip_key = row[props['chip_key']]
    new_packet.packet_type = row[props['type']]
    new_packet.chipid = row[props['chipid']]
    new_packet.parity_bit_value = row[props['parity']]
    new_packet.register_address = row[props['register']]
    new_packet.register_data = row[props['value']]
    new_packet.direction = row[props['direction']]
    assert new_packet == config_read_packet

def test_to_file_v1_0_timestamp_packet(tmpfile, timestamp_packet):
    to_file(tmpfile, [timestamp_packet], version='1.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 1
    row = f['packets'][0]
    props = dtype_property_index_lookup['1.0']['packets']
    assert row[1] == 4  # packet_type
    new_packet = TimestampPacket()
    new_packet.timestamp = row[props['timestamp']]
    assert new_packet == timestamp_packet

def test_to_file_v1_0_message_packet(tmpfile, message_packet,
        data_packet):
    to_file(tmpfile, [data_packet, message_packet], version='1.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 2
    row = f['packets'][1]
    props = dtype_property_index_lookup['1.0']['packets']
    message_props = dtype_property_index_lookup['1.0']['messages']
    assert row[props['type']] == 5
    assert row[props['counter']] == 0
    assert row[props['timestamp']] == 1234567
    assert len(f['messages']) == 1
    message_row = f['messages'][0]
    assert message_row[message_props['index']] == 0
    assert message_row[message_props['message']] == b'Hello, World!'
    assert message_row[message_props['timestamp']] == 1234567

def test_to_file_v1_0_many_packets(tmpfile, data_packet, config_read_packet,
        timestamp_packet, message_packet):
    to_file(tmpfile, [data_packet, config_read_packet,
        timestamp_packet, message_packet], version='1.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 4
    assert len(f['messages']) == 1

def test_from_file_v1_0_many_packets(tmpfile, data_packet,
        config_read_packet, timestamp_packet, message_packet):
    packets = [data_packet, config_read_packet, timestamp_packet,
            message_packet]
    to_file(tmpfile, packets, version='1.0')
    new_packets_dict = from_file(tmpfile)
    assert new_packets_dict['created']
    assert new_packets_dict['version']
    assert new_packets_dict['modified']
    new_packets = new_packets_dict['packets']
    assert new_packets[0] == data_packet
    assert new_packets[1] == config_read_packet
    assert new_packets[2] == timestamp_packet
    assert new_packets[3] == message_packet

def test_to_file_v2_0_empty(tmpfile):
    to_file(tmpfile, [], version='2.0')
    f = h5py.File(tmpfile, 'r')
    assert f['_header']
    assert f['_header'].attrs['version']
    assert f['_header'].attrs['created']
    assert f['_header'].attrs['modified']
    assert f['packets']

def test_to_file_v2_0_data_packet(tmpfile, data_packet_v2):
    to_file(tmpfile, [data_packet_v2], version='2.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 1
    row = f['packets'][0]
    props = dtype_property_index_lookup['2.0']['packets']
    new_packet = Packet_v2()
    new_packet.chip_key = Key(row[props['io_group']], row[props['io_channel']], row[props['chip_id']])
    new_packet.packet_type = row[props['packet_type']]
    new_packet.trigger_type = row[props['trigger_type']]
    new_packet.chip_id = row[props['chip_id']]
    new_packet.parity = row[props['parity']]
    new_packet.channel_id = row[props['channel_id']]
    new_packet.timestamp = row[props['timestamp']]
    new_packet.dataword = row[props['dataword']]
    new_packet.local_fifo = row[props['local_fifo']]
    new_packet.shared_fifo = row[props['shared_fifo']]
    new_packet.direction = row[props['direction']]
    assert new_packet.timestamp == data_packet_v2.timestamp
    assert new_packet == data_packet_v2

def test_to_file_v2_0_config_read_packet(tmpfile, config_read_packet_v2):
    to_file(tmpfile, [config_read_packet_v2], version='2.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 1
    row = f['packets'][0]
    props = dtype_property_index_lookup['2.0']['packets']
    new_packet = Packet_v2()
    new_packet.chip_key = Key(row[props['io_group']], row[props['io_channel']], row[props['chip_id']])
    new_packet.packet_type = row[props['packet_type']]
    new_packet.parity = row[props['parity']]
    new_packet.register_address = row[props['register_address']]
    new_packet.register_data = row[props['register_data']]
    new_packet.direction = row[props['direction']]
    print(new_packet)
    print(config_read_packet_v2)
    assert new_packet == config_read_packet_v2

def test_to_file_v2_0_timestamp_packet(tmpfile, timestamp_packet):
    to_file(tmpfile, [timestamp_packet], version='2.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 1
    row = f['packets'][0]
    props = dtype_property_index_lookup['2.0']['packets']
    assert row[3] == 4  # packet_type
    new_packet = TimestampPacket()
    new_packet.timestamp = row[props['timestamp']]
    assert new_packet == timestamp_packet

def test_to_file_v2_0_message_packet(tmpfile, message_packet,
        data_packet_v2):
    to_file(tmpfile, [data_packet_v2, message_packet], version='2.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 2
    row = f['packets'][1]
    props = dtype_property_index_lookup['2.0']['packets']
    message_props = dtype_property_index_lookup['2.0']['messages']
    assert row[props['packet_type']] == 5
    assert row[props['timestamp']] == 1234567
    assert len(f['messages']) == 1
    message_row = f['messages'][0]
    assert message_row[message_props['index']] == 0
    assert message_row[message_props['message']] == b'Hello, World!'
    assert message_row[message_props['timestamp']] == 1234567

def test_to_file_v2_0_many_packets(tmpfile, data_packet_v2, config_read_packet_v2,
        timestamp_packet, message_packet):
    to_file(tmpfile, [data_packet_v2, config_read_packet_v2,
        timestamp_packet, message_packet], version='2.0')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 4
    assert len(f['messages']) == 1

def test_from_file_v2_0_many_packets(tmpfile, data_packet_v2,
        config_read_packet_v2, timestamp_packet, message_packet):
    packets = [data_packet_v2, config_read_packet_v2, timestamp_packet,
            message_packet]
    to_file(tmpfile, packets, version='2.0')
    new_packets_dict = from_file(tmpfile)
    assert new_packets_dict['created']
    assert new_packets_dict['version']
    assert new_packets_dict['modified']
    new_packets = new_packets_dict['packets']
    _ = [print(str(packet) +'\n' + str(packets[i])) for i,packet in enumerate(new_packets)]
    assert new_packets[0] == data_packet_v2
    assert new_packets[1] == config_read_packet_v2
    assert new_packets[2] == timestamp_packet
    assert new_packets[3] == message_packet

def test_to_file_v2_2_many_packets(tmpfile, data_packet_v2, config_read_packet_v2,
                                   timestamp_packet, message_packet, sync_packet,
                                   trigger_packet):
    to_file(tmpfile, [data_packet_v2, config_read_packet_v2,
                      timestamp_packet, message_packet, sync_packet,
                      trigger_packet],
            version='2.2')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 6
    assert len(f['messages']) == 1

def test_from_file_v2_2_many_packets(tmpfile, data_packet_v2,
                                     config_read_packet_v2, timestamp_packet,
                                     message_packet, sync_packet, trigger_packet):
    packets = [data_packet_v2, config_read_packet_v2, timestamp_packet,
               message_packet, sync_packet, trigger_packet]
    to_file(tmpfile, packets, version='2.2')
    new_packets_dict = from_file(tmpfile)
    assert new_packets_dict['created']
    assert new_packets_dict['version']
    assert new_packets_dict['modified']
    new_packets = new_packets_dict['packets']
    _ = [print(str(packet) +'\n' + str(packets[i])) for i,packet in enumerate(new_packets)]
    assert new_packets[0] == data_packet_v2
    assert new_packets[1] == config_read_packet_v2
    assert new_packets[2] == timestamp_packet
    assert new_packets[3] == message_packet
    assert new_packets[4] == sync_packet
    assert new_packets[5] == trigger_packet

def test_to_file_v2_3_many_packets(tmpfile, data_packet_v2, config_read_packet_v2,
                                   timestamp_packet, message_packet, sync_packet,
                                   trigger_packet):
    to_file(tmpfile, [data_packet_v2, config_read_packet_v2,
                      timestamp_packet, message_packet, sync_packet,
                      trigger_packet],
            version='2.3')
    f = h5py.File(tmpfile, 'r')
    assert len(f['packets']) == 6
    assert len(f['messages']) == 1

def test_from_file_v2_3_many_packets(tmpfile, data_packet_v2,
                                     config_read_packet_v2, timestamp_packet,
                                     message_packet, sync_packet, trigger_packet):
    packets = [data_packet_v2, config_read_packet_v2, timestamp_packet,
               message_packet, sync_packet, trigger_packet]
    to_file(tmpfile, packets, version='2.3')
    new_packets_dict = from_file(tmpfile)
    assert new_packets_dict['created']
    assert new_packets_dict['version']
    assert new_packets_dict['modified']
    new_packets = new_packets_dict['packets']
    _ = [print(str(packet) +'\n' + str(packets[i])) for i,packet in enumerate(new_packets)]
    assert new_packets[0] == data_packet_v2
    assert new_packets[1] == config_read_packet_v2
    assert new_packets[2] == timestamp_packet
    assert new_packets[3] == message_packet
    assert new_packets[4] == sync_packet
    assert new_packets[5] == trigger_packet

def test_to_file_v2_4_chips(tmpfile, chip):
    chips = [copy.deepcopy(chip) for i in range(10)]
    for i,chip in enumerate(chips):
        chip.chip_id = i
    chips[0].config.pixel_trim_dac[12] = 0
    chips[1].config.threshold_global = 1
    to_file(tmpfile, chip_list=chips, version='2.4')
    new_chips = from_file(tmpfile, load_configs=True)['configs']
    assert [chip.chip_key for chip in chips] == [chip.chip_key for chip in new_chips]
    assert [chip.config for chip in chips] == [chip.config for chip in new_chips]
    assert new_chips[0].config.pixel_trim_dac[12] == chips[0].config.pixel_trim_dac[12]
    assert new_chips[1].config.threshold_global == chips[1].config.threshold_global

    new_chips = from_file(tmpfile, load_configs=slice(1,4))['configs']
    assert len(new_chips) == 3
    assert new_chips[0].chip_key == chips[1].chip_key

def test_from_file_incompatible(tmpfile):
    to_file(tmpfile, [], version='0.0')
    with pytest.raises(RuntimeError):
        from_file(tmpfile, version='1.0')
        pytest.fail('Should identify incompatible version')
