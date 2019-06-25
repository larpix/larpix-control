'''
Tests for basic logging functionality

'''
from __future__ import print_function
import pytest
import os
import numpy as np
from larpix.larpix import Packet, Controller, Chip, TimestampPacket
from larpix.io.fakeio import FakeIO
from larpix.logger.h5_logger import HDF5Logger

def test_enable(tmpdir):
    logger = HDF5Logger(directory=str(tmpdir),buffer_length=1)
    logger.open()

    logger.enable()
    assert logger.is_enabled()
    logger.record([Packet()])
    assert len(logger._buffer['raw_packet']) == 1

def test_disable(tmpdir):
    logger = HDF5Logger(directory=str(tmpdir))
    logger.open()

    logger.disable()
    assert not logger.is_enabled()
    logger.record([Packet()])
    assert len(logger._buffer['raw_packet']) == 0

def test_open(tmpdir):
    logger = HDF5Logger(directory=str(tmpdir))
    logger.open()

    assert logger.is_enabled()
    assert logger.is_open()

def test_flush(tmpdir):
    logger = HDF5Logger(directory=str(tmpdir), buffer_length=5)
    logger.open()

    logger.record([Packet()])
    assert len(logger._buffer['raw_packet']) == 1
    logger.flush()
    assert len(logger._buffer['raw_packet']) == 0
    logger.record([Packet()]*5)
    assert len(logger._buffer['raw_packet']) == 5
    logger.record([Packet()])
    assert len(logger._buffer['raw_packet']) == 0

def test_close(tmpdir):
    logger = HDF5Logger(directory=str(tmpdir))
    logger.open()

    logger.close()
    assert not logger.is_enabled()
    assert not logger.is_open()

def test_record(tmpdir):
    logger = HDF5Logger(directory=str(tmpdir))
    logger.open()

    logger.record([Packet()])
    assert len(logger._buffer['raw_packet']) == 1
    logger.record([TimestampPacket(timestamp=123)])
    assert len(logger._buffer['raw_packet']) == 2

@pytest.mark.filterwarnings("ignore:no IO object")
def test_controller_write_capture(tmpdir):
    controller = Controller()
    controller.logger = HDF5Logger(directory=str(tmpdir), buffer_length=1)
    controller.logger.open()
    controller.chips[0] = Chip(2, 0)
    chip = controller.chips[0]
    controller.write_configuration(0, 0)
    packet = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)[0]
    assert len(controller.logger._buffer) == 1

def test_controller_read_capture(tmpdir):
    controller = Controller()
    controller.io = FakeIO()
    controller.io.queue.append(([Packet()], b'\x00\x00'))
    controller.logger = HDF5Logger(directory=str(tmpdir), buffer_length=1)
    controller.logger.open()
    controller.run(0.1,'test')
    assert len(controller.logger._buffer) == 1
