'''
Tests for larpix.io.zmq_io module

'''
from __future__ import print_function
import pytest
import os
import json
from larpix.larpix import Packet, Key
from larpix.io.zmq_io import ZMQ_IO
from larpix.format.message_format import dataserver_message_encode

@pytest.fixture
def io_config(tmpdir):
    filename = str(tmpdir.join('test_conf.json'))
    config_dict = {
            "_config_type": "io",
            "io_class": "ZMQ_IO",
            "io_group": [
                [1, "192.0.2.1"]
            ]
        }
    with open(filename,'w') as of:
        json.dump(config_dict, of)
    return filename

@pytest.fixture
def zmq_io_obj(io_config):
    return ZMQ_IO(io_config)

def test_encode(zmq_io_obj):
    chip_id = 64
    io_chain = 1
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = Key(1, io_chain, chip_id)
    test_bytes = b'0x0006050403020100 1'
    expected = [test_bytes]
    assert zmq_io_obj.encode([test_packet]) == expected

def test_decode(zmq_io_obj):
    chip_id = 64
    io_chain = 1
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = Key(1, io_chain, chip_id)
    test_bytes = dataserver_message_encode([test_packet])
    expected = [test_packet]
    assert zmq_io_obj.decode(test_bytes) == expected
