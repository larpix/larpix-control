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
    logger.enable()
    assert logger.is_enabled()
    logger.record(['test'])
    assert len(logger._buffer) == 1

def test_disable():
    logger = StdoutLogger()
    logger.disable()
    assert not logger.is_enabled()
    logger.record(['test'])
    assert len(logger._buffer) == 0

def test_flush():
    logger = StdoutLogger(buffer_length=5)
    logger.enable()
    logger.record(['test'])
    assert len(logger._buffer) == 1
    logger.flush()
    assert len(logger._buffer) == 0
    logger.record(['test']*5)
    assert len(logger._buffer) == 5
    logger.record(['test'])
    assert len(logger._buffer) == 0

def test_record():
    logger = StdoutLogger(buffer_length=1)
    logger.enable()
    logger.record(['test'])
    assert logger._buffer[0] == 'Record: test'

@pytest.mark.filterwarnings("ignore:no IO object")
def test_controller_write_capture(capfd, chip):
    controller = Controller()
    controller.logger = StdoutLogger(buffer_length=100)
    controller.logger.enable()
    controller.chips[chip.chip_key] = chip
    controller.write_configuration(chip.chip_key, 0)
    packet = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)[0]
    assert len(controller.logger._buffer) == 1

def test_controller_read_capture(capfd):
    controller = Controller()
    controller.io = FakeIO()
    controller.io.queue.append(([Packet()], b'\x00\x00'))
    controller.logger = StdoutLogger(buffer_length=100)
    controller.logger.enable()
    controller.run(0.1,'test')
    assert len(controller.logger._buffer) == 1
