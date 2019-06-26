'''
Tests for larpix.io.multizmq_io module

'''
from __future__ import print_function
import pytest
import os
from larpix.larpix import Packet
from larpix.io.multizmq_io import MultiZMQ_IO
from larpix.format.message_format import dataserver_message_decode, dataserver_message_encode

def test_generate_chip_key():
    chip_id = 125
    io_chain = 2
    address = 'localhost'
    expected = '{}/{}/{}'.format(address, io_chain, chip_id)
    assert MultiZMQ_IO.is_valid_chip_key(expected)
    assert MultiZMQ_IO.generate_chip_key(address=address, chip_id=chip_id, io_chain=io_chain)

def test_parse_chip_key():
    chip_id = 62
    io_chain = 0
    address = 'localhost'
    expected = {
        'chip_id': chip_id,
        'io_chain': io_chain,
        'address': address
    }
    key = '{}/{}/{}'.format(address, io_chain, chip_id)
    assert MultiZMQ_IO.is_valid_chip_key(key)
    assert MultiZMQ_IO.parse_chip_key(key) == expected

def test_encode():
    chip_id = 64
    io_chain = 1
    address = 'localhost'
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = MultiZMQ_IO.generate_chip_key(address=address, chip_id=chip_id, io_chain=io_chain)
    test_bytes = b'0x0006050403020100 1'
    expected = [test_bytes]
    assert MultiZMQ_IO.encode([test_packet]) == expected

def test_decode():
    chip_id = 64
    io_chain = 1
    address = 'localhost'
    test_packet = Packet(b'\x00\x01\x02\x03\x04\x05\x06')
    test_packet.chip_key = MultiZMQ_IO.generate_chip_key(address=address, chip_id=chip_id, io_chain=io_chain)
    test_bytes = dataserver_message_encode([test_packet])
    expected = [test_packet]
    assert MultiZMQ_IO.decode(test_bytes, address=address) == expected
