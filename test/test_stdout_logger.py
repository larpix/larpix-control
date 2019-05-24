'''
Tests for basic logging functionality

'''
from __future__ import print_function
import pytest
from larpix.larpix import Packet, Controller, Chip
from larpix.io.fakeio import FakeIO
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

def test_controller_write_capture(capfd):
    controller = Controller()
    controller.logger = StdoutLogger(buffer_length=1)
    controller.logger.open()
    controller.chips[0] = Chip(2, 0)
    chip = controller.chips[0]
    controller.write_configuration(0, 0)
    packet = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)[0]
    assert len(controller.logger._buffer) == 1

def test_controller_read_capture(capfd):
    controller = Controller()
    controller.io = FakeIO()
    controller.io.queue.append(([Packet()], b'\x00\x00'))
    controller.logger = StdoutLogger(buffer_length=1)
    controller.logger.open()
    controller.run(0.1,'test')
    assert len(controller.logger._buffer) == 1
