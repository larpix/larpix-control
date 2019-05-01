'''
Tests for basic logging functionality

'''
from __future__ import print_function
import pytest
import os
import numpy as np
from larpix.larpix import Packet
from larpix.logger.h5_logger import HDF5Logger

test_filename = '.test.h5'
def fresh_temp_file(func):
    def new_func(*args,**kwargs):
        try:
            os.remove(test_filename)
        except:
            pass
        return_value = func(*args, **kwargs)
        try:
            os.remove(test_filename)
        except:
            pass
    return new_func

@fresh_temp_file
def test_enable():
    logger = HDF5Logger(filename=test_filename,buffer_length=1)
    logger.open()

    logger.enable()
    assert logger.is_enabled()
    logger.record([Packet()])
    assert len(logger._buffer['raw_packet']) == 1

@fresh_temp_file
def test_disable():
    logger = HDF5Logger(filename=test_filename)
    logger.open()

    logger.disable()
    assert not logger.is_enabled()
    logger.record([Packet()])
    assert len(logger._buffer['raw_packet']) == 0

@fresh_temp_file
def test_open():
    logger = HDF5Logger(filename=test_filename)
    logger.open()

    assert logger.is_enabled()
    assert logger.is_open()

@fresh_temp_file
def test_flush():
    logger = HDF5Logger(filename=test_filename, buffer_length=5)
    logger.open()

    logger.record([Packet()])
    assert len(logger._buffer['raw_packet']) == 1
    logger.flush()
    assert len(logger._buffer['raw_packet']) == 0
    logger.record([Packet()]*5)
    assert len(logger._buffer['raw_packet']) == 5
    logger.record([Packet()])
    assert len(logger._buffer['raw_packet']) == 0

@fresh_temp_file
def test_close():
    logger = HDF5Logger(filename=test_filename)
    logger.open()

    logger.close()
    assert not logger.is_enabled()
    assert not logger.is_open()

@fresh_temp_file
def test_record():
    logger = HDF5Logger(filename=test_filename, buffer_length=1)
    logger.open()

    logger.record([Packet()], timestamp=5.0)
    assert logger._buffer['raw_packet'][0] == HDF5Logger.encode(Packet(), timestamp=5.0)
