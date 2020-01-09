'''
Tests for basic logging functionality

'''
from __future__ import print_function
import pytest
import os
import numpy as np
from larpix.larpix import Packet_v1, Packet_v2, Controller, Chip, TimestampPacket
from larpix.io.fakeio import FakeIO
from larpix.logger.h5_logger import HDF5Logger

def test_enable(tmpdir):
    logger = HDF5Logger(directory=str(tmpdir))
    assert not logger.is_enabled()
    logger.record([Packet_v2()])
    assert len(logger._buffer['packets']) == 0
    logger.enable()
    assert logger.is_enabled()
    logger.record([Packet_v2()])
    assert len(logger._buffer['packets']) == 1

def test_disable(tmpdir):
    logger =HDF5Logger(directory=str(tmpdir), enabled=True)
    logger.disable()
    assert not logger.is_enabled()
    logger.record([Packet_v2()])
    assert len(logger._buffer['packets']) == 0

def test_flush(tmpdir):
    logger = HDF5Logger(directory=str(tmpdir), buffer_length=5,
            enabled=True)
    logger.record([Packet_v2()])
    assert len(logger._buffer['packets']) == 1
    logger.flush()
    assert len(logger._buffer['packets']) == 0
    logger.record([Packet_v2()]*5)
    assert len(logger._buffer['packets']) == 5
    logger.record([Packet_v2()])
    assert len(logger._buffer['packets']) == 0

def test_record(tmpdir):
    logger = HDF5Logger(directory=str(tmpdir), enabled=True)
    logger.record([Packet_v2()])
    assert len(logger._buffer['packets']) == 1
    logger.record([TimestampPacket(timestamp=123)])
    assert len(logger._buffer['packets']) == 2

@pytest.mark.filterwarnings("ignore:no IO object")
def test_controller_write_capture(tmpdir, chip):
    controller = Controller()
    controller.logger = HDF5Logger(directory=str(tmpdir), buffer_length=1)
    controller.logger.enable()
    controller.chips[chip.chip_key] = chip
    controller.write_configuration(chip.chip_key, 0)
    packet = chip.get_configuration_write_packets()[0]
    assert len(controller.logger._buffer['packets']) == 1

def test_controller_read_capture(tmpdir):
    controller = Controller()
    controller.io = FakeIO()
    controller.io.queue.append(([Packet_v2()], b'\x00\x00'))
    controller.logger = HDF5Logger(directory=str(tmpdir), buffer_length=1)
    controller.logger.enable()
    controller.run(0.1,'test')
    assert len(controller.logger._buffer['packets']) == 1
