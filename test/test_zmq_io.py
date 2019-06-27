'''
Tests for larpix.io.zmq_io module

'''
from __future__ import print_function
import pytest
import os
from larpix.larpix import Packet, Key
from larpix.io.zmq_io import ZMQ_IO
from larpix.format.message_format import dataserver_message_encode

@pytest.mark.skip
def test_generate_chip_key():
    chip_id = 125
    io_chain = 2
    io_group = 1
    expected = Key('{}-{}-{}'.format(io_group, io_chain, chip_id))
    assert ZMQ_IO.generate_chip_key(chip_id=chip_id, io_chain=io_chain, io_group=io_group)

@pytest.mark.skip
def test_parse_chip_key():
    chip_id = 62
    io_chain = 2
    io_group = 1
    expected = {
        'chip_id': chip_id,
        'io_chain': io_chain - 1
    }
    key = Key('{}-{}-{}'.format(io_group, io_chain, chip_id))
    assert ZMQ_IO.parse_chip_key(key) == expected

@pytest.mark.skip
def test_encode():
    chip_id = 64
    io_chain = 1
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = ZMQ_IO.generate_chip_key(chip_id=chip_id, io_chain=io_chain)
    test_bytes = b'0x0006050403020100 1'
    expected = [test_bytes]
    assert ZMQ_IO.encode([test_packet]) == expected

@pytest.mark.skip
def test_decode():
    chip_id = 64
    io_chain = 1
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = ZMQ_IO.generate_chip_key(chip_id=chip_id, io_chain=io_chain)
    test_bytes = dataserver_message_encode([test_packet])
    expected = [test_packet]
    assert ZMQ_IO.decode(test_bytes) == expected
