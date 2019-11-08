'''
Tests for larpix.io.multizmq_io module

'''
from __future__ import print_function
import pytest
import os
import json
from larpix.larpix import Packet, Key, Packet_v1
from larpix.io.multizmq_io import MultiZMQ_IO
from larpix.format.message_format import dataserver_message_decode, dataserver_message_encode

@pytest.fixture
def io_config(tmpdir):
    filename = str(tmpdir.join('test_conf.json'))
    config_dict = {
            "_config_type": "io",
            "io_class": "MultiZMQ_IO",
            "io_group": [
                [1, "192.0.2.1"],
                [2, "192.0.2.2"]
            ]
        }
    with open(filename,'w') as of:
        json.dump(config_dict, of)
    return filename

@pytest.fixture
def multizmq_io_obj(io_config):
    return MultiZMQ_IO(io_config)

def test_encode(multizmq_io_obj):
    chip_id = 64
    io_chain = 1
    io_group = list(multizmq_io_obj._io_group_table)[0]
    test_packet = Packet(b'\x01'*Packet.num_bytes)
    test_packet.io_group = io_group
    test_packet.io_channel = io_chain
    test_bytes = b'0x0101010101010101 1'
    if Packet == Packet_v1:
        test_bytes = b'0x0001010101010101 1'
    expected = [test_bytes]
    assert multizmq_io_obj.encode([test_packet]) == expected

def test_decode(multizmq_io_obj):
    chip_id = 64
    io_chain = 1
    io_group = list(multizmq_io_obj._io_group_table)[0]
    address = str(multizmq_io_obj._io_group_table[io_group])
    test_packet = Packet(b'\x01'*Packet.num_bytes)
    test_packet.io_group = io_group
    test_packet.io_channel = io_chain
    test_bytes = dataserver_message_encode([test_packet])
    expected = [test_packet]
    assert multizmq_io_obj.decode(test_bytes, address=address) == expected
