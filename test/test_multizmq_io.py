'''
Tests for larpix.io.multizmq_io module

'''
from __future__ import print_function
import pytest
import os
from larpix.larpix import Packet
from larpix.io.multizmq_io import MultiZMQ_IO

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
    test_bytes = b'\x00\x01\x02\x03\x04\x05\x06'
    expected = [b'0x0006050403020100 0']
    assert MultiZMQ_IO.encode([Packet(test_bytes)]) == expected

def test_decode():
    test_bytes = b'\x00\x06\x05\x04\x03\x02\x01\x00'
    expected = [Packet(test_bytes[:-1])]
    assert MultiZMQ_IO.decode([test_bytes]) == expected
