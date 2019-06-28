'''
Tests for larpix.io.multizmq_io module

'''
from __future__ import print_function
import pytest
import os
import json
from larpix.larpix import Packet, Key
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

def test_generate_chip_key(multizmq_io_obj):
    chip_id = 125
    io_chain = 2
    address = str(list(multizmq_io_obj._io_group_table.inv.keys())[0])
    expected = '{}-{}-{}'.format(multizmq_io_obj._io_group_table.inv[address], io_chain, chip_id)
    assert multizmq_io_obj.generate_chip_key(address=address, chip_id=chip_id, io_chain=io_chain)

def test_parse_chip_key(multizmq_io_obj):

    chip_id = 62
    io_chain = 1
    address = str(list(multizmq_io_obj._io_group_table.inv.keys())[0])
    expected = {
        'chip_id': chip_id,
        'io_chain': io_chain,
        'address': address
    }
    key = Key('{}-{}-{}'.format(multizmq_io_obj._io_group_table.inv[address], io_chain, chip_id))
    assert multizmq_io_obj.parse_chip_key(key) == expected

def test_encode(multizmq_io_obj):
    chip_id = 64
    io_chain = 1
    address = str(list(multizmq_io_obj._io_group_table.inv.keys())[0])
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = multizmq_io_obj.generate_chip_key(address=address, chip_id=chip_id, io_chain=io_chain)
    test_bytes = b'0x0006050403020100 1'
    expected = [test_bytes]
    assert multizmq_io_obj.encode([test_packet]) == expected

def test_decode(multizmq_io_obj):
    chip_id = 64
    io_chain = 1
    address = str(list(multizmq_io_obj._io_group_table.inv.keys())[0])
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = multizmq_io_obj.generate_chip_key(address=address, chip_id=chip_id, io_chain=io_chain)
    test_bytes = dataserver_message_encode([test_packet])
    expected = [test_packet]
    assert multizmq_io_obj.decode(test_bytes, address=address) == expected
