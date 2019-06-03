'''
Tests for larpix.io.zmq_io module

'''
from __future__ import print_function
import pytest
import os
from larpix.larpix import Packet
from larpix.io.zmq_io import ZMQ_IO

def test_encode():
    test_bytes = b'\x00\x01\x02\x03\x04\x05\x06'
    expected = [b'0x0006050403020100 0']
    assert ZMQ_IO.encode([Packet(test_bytes)]) == expected

def test_decode():
    test_bytes = b'\x00\x06\x05\x04\x03\x02\x01\x00'
    expected = [Packet(test_bytes[:-1])]
    assert ZMQ_IO.decode([test_bytes]) == expected
