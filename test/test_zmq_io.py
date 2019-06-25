'''
Tests for larpix.io.zmq_io module

'''
from __future__ import print_function
import pytest
import os
from larpix.larpix import Packet
from larpix.io.zmq_io import ZMQ_IO
from larpix.format.message_format import dataserver_message_encode

def test_generate_chip_key():
    chip_id = 125
    io_chain = 2
    expected = '{}-{}'.format(io_chain, chip_id)
    assert ZMQ_IO.is_valid_chip_key(expected)
    assert ZMQ_IO.generate_chip_key(chip_id=chip_id, io_chain=io_chain)

def test_parse_chip_key():
    chip_id = 62
    io_chain = 0
    expected = {
        'chip_id': chip_id,
        'io_chain': io_chain
    }
    key = '{}-{}'.format(io_chain, chip_id)
    assert ZMQ_IO.is_valid_chip_key(key)
    assert ZMQ_IO.parse_chip_key(key) == expected

def test_encode():
    chip_id = 64
    io_chain = 1
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = ZMQ_IO.generate_chip_key(chip_id=chip_id, io_chain=io_chain)
    test_bytes = b'0x0006050403020100 1'
    expected = [test_bytes]
    assert ZMQ_IO.encode([test_packet]) == expected

def test_decode():
    chip_id = 64
    io_chain = 1
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = ZMQ_IO.generate_chip_key(chip_id=chip_id, io_chain=io_chain)
    test_bytes = dataserver_message_encode([test_packet])
    expected = [test_packet]
    assert ZMQ_IO.decode(test_bytes) == expected
