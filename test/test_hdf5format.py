from __future__ import print_function

import pytest
import h5py

from larpix.larpix import (Packet, PacketCollection, TimestampPacket,
        DirectionPacket)
from larpix.format.hdf5format import to_file, from_file

@pytest.fixture
def tmpfile(tmpdir):
    return str(tmpdir.join('test.h5'))

@pytest.fixture
def data_packet():
    p = Packet()
    p.packet_type = Packet.DATA_PACKET
    p.chipid = 123
    p.channel = 7
    p.timestamp = 123456
    p.dataword = 120
    p.fifo_half_flag = 1
    p.assign_parity()
    p.chip_key = 'hello'
    return p

@pytest.fixture
def config_read_packet():
    p = Packet()
    p.packet_type = Packet.CONFIG_READ_PACKET
    p.chipid = 123
    p.register_address = 10
    p.register_data = 23
    p.assign_parity()
    p.chip_key = 'hello'
    return p

@pytest.fixture
def timestamp_packet():
    return TimestampPacket(timestamp=12345)

@pytest.fixture
def direction_packet():
    return DirectionPacket(direction=1)

def test_to_file_empty(tmpfile):
    to_file(tmpfile, [])
    f = h5py.File(tmpfile, 'r')
    assert f['_header']
    assert f['_header'].attrs['version']
    assert f['_header'].attrs['created']
    assert f['_header'].attrs['modified']
    assert f['raw_packet']

def test_to_file_data_packet(tmpfile, data_packet):
    to_file(tmpfile, [data_packet])
    f = h5py.File(tmpfile, 'r')
    assert len(f['raw_packet']) == 1
    row = f['raw_packet'][0]
    new_packet = Packet()
    new_packet.chip_key = row[0]
    new_packet.packet_type = row[1]
    new_packet.chipid = row[2]
    new_packet.parity_bit_value = row[3]
    new_packet.channel = row[5]
    new_packet.timestamp = row[6]
    new_packet.dataword = row[7]
    new_packet.fifo_half_flag = row[8]
    new_packet.fifo_full_flag = row[9]
    assert new_packet == data_packet

def test_to_file_config_read_packet(tmpfile, config_read_packet):
    to_file(tmpfile, [config_read_packet])
    f = h5py.File(tmpfile, 'r')
    assert len(f['raw_packet']) == 1
    row = f['raw_packet'][0]
    new_packet = Packet()
    new_packet.chip_key = row[0]
    new_packet.packet_type = row[1]
    new_packet.chipid = row[2]
    new_packet.parity_bit_value = row[3]
    new_packet.register_address = row[10]
    new_packet.register_data = row[11]
    assert new_packet == config_read_packet

def test_to_file_timestamp_packet(tmpfile, timestamp_packet):
    to_file(tmpfile, [timestamp_packet])
    f = h5py.File(tmpfile, 'r')
    assert len(f['raw_packet']) == 1
    row = f['raw_packet'][0]
    assert row[1] == 4  # packet_type
    new_packet = TimestampPacket()
    new_packet.timestamp = row[6]
    assert new_packet == timestamp_packet

def test_to_file_direction_packet(tmpfile, direction_packet):
    to_file(tmpfile, [direction_packet])
    f = h5py.File(tmpfile, 'r')
    assert len(f['raw_packet']) == 1
    row = f['raw_packet'][0]
    assert row[1] == 5  # packet_type
    new_packet = DirectionPacket()
    new_packet.direction = row[13]
    assert new_packet == direction_packet

def test_to_file_many_packets(tmpfile, data_packet, config_read_packet,
        timestamp_packet, direction_packet):
    to_file(tmpfile, [data_packet, config_read_packet, timestamp_packet,
        direction_packet])
    f = h5py.File(tmpfile, 'r')
    assert len(f['raw_packet']) == 4

def test_from_file_many_packets(tmpfile, data_packet,
        config_read_packet, timestamp_packet, direction_packet):
    packets = [data_packet, config_read_packet, timestamp_packet,
            direction_packet]
    to_file(tmpfile, packets)
    new_packets_dict = from_file(tmpfile)
    assert new_packets_dict['created']
    assert new_packets_dict['version']
    assert new_packets_dict['modified']
    new_packets = new_packets_dict['packets']
    assert new_packets[0] == data_packet
    assert new_packets[1] == config_read_packet
    assert new_packets[2] == timestamp_packet
    assert new_packets[3] == direction_packet
