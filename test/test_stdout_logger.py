'''
Tests for basic logging functionality

'''
from __future__ import print_function
import pytest
from larpix.fakeio import FakeIO
from larpix.larpix import Packet
from larpix.logger.stdout_logger import StdoutLogger

def test_enable():
    logger = StdoutLogger(buffer_length=1)
    logger.open()

    logger.enable()
    assert logger.is_enabled()
    logger.record(['test'])
    assert len(logger._buffer) == 1

def test_disable():
    logger = StdoutLogger()
    logger.open()

    logger.disable()
    assert not logger.is_enabled()
    logger.record(['test'])
    assert len(logger._buffer) == 0

def test_open():
    logger = StdoutLogger()
    logger.open()

    assert logger.is_enabled()
    assert logger.is_open()

def test_flush():
    logger = StdoutLogger(buffer_length=5)
    logger.open()

    logger.record(['test'])
    assert len(logger._buffer) == 1
    logger.flush()
    assert len(logger._buffer) == 0
    logger.record(['test']*5)
    assert len(logger._buffer) == 5
    logger.record(['test'])
    assert len(logger._buffer) == 0

def test_close():
    logger = StdoutLogger()
    logger.open()

    logger.close()
    assert not logger.is_enabled()
    assert not logger.is_open()

def test_record():
    logger = StdoutLogger(buffer_length=1)
    logger.open()

    logger.record(['test'], timestamp=5.0)
    assert logger._buffer[0] == 'Record 5.0: test'
