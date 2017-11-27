'''
Use the pytest framework to write tests for the simulation module.

This is not quite unit testing because all of the methods are highly
coupled. So I'm doing the best I can to make sure all the functionality
is tested.

'''
from __future__ import print_function
import pytest
from collections import deque
from larpix.larpix import (Packet)
from larpix.simulation import (MockLArPix, MockSerial, MockFormatter)

def test_MockLArPix_receive_not_mine():
    chip = MockLArPix(1, 0)
    nextchip = MockLArPix(2, 0)
    chip.next = nextchip
    packet = Packet()
    packet.chipid = 100
    packet.assign_parity()
    result = chip.receive(packet)
    expected = {'sent': packet}
    assert result == expected

def test_MockLArPix_receive_config_read():
    chip = MockLArPix(1, 0)
    packet = Packet()
    packet.chipid = 1
    packet.packet_type = Packet.CONFIG_READ_PACKET
    packet.assign_parity()
    result = chip.receive(packet)
    expected_packet = Packet()
    expected_packet.chipid = 1
    expected_packet.packet_type = Packet.CONFIG_READ_PACKET
    expected_packet.register_data = chip.config.pixel_trim_thresholds[0]
    expected_packet.assign_parity()
    expected = {'sent': expected_packet}
    assert result == expected

def test_MockLArPix_receive_config_write():
    chip = MockLArPix(1, 0)
    packet = Packet()
    packet.chipid = 1
    packet.packet_type = Packet.CONFIG_WRITE_PACKET
    packet.register_data = 3
    packet.assign_parity()
    result = chip.receive(packet)
    expected = None
    assert result == expected
    result_config = chip.config.pixel_trim_thresholds[0]
    expected_config = 3
    assert result == expected

def test_MockLArPix_send_to_next_chip():
    chip = MockLArPix(1, 0)
    nextchip = MockLArPix(2, 0)
    chip.next = nextchip
    packet = Packet()
    packet.assign_parity()
    result = chip.send(packet)
    expected = {'sent': packet}
    assert result == expected

def test_MockLArPix_send_to_formatter():
    chip = MockLArPix(1, 0)
    formatter = MockFormatter()
    chip.next = formatter
    packet = Packet()
    packet.assign_parity()
    result = chip.send(packet)
    expected = packet
    assert result == expected

def test_MockLArPix_timestamp():
    chip = MockLArPix(0, 0)
    timestamp1 = chip.timestamp()
    timestamp2 = chip.timestamp()
    rollover = timestamp2 < timestamp1
    if rollover:
        assert timestamp1 - timestamp2 > 9e5
    else:
        assert True

def test_MockLArPix_digitize():
    chip = MockLArPix(0, 0)
    result = chip.digitize(chip.vcm)
    expected = 0
    assert result == expected
    result = chip.digitize(chip.vref)
    expected = 255
    assert result == expected
    result = chip.digitize(chip.vcm + (chip.vref - chip.vcm)/2)
    expected = 128
    assert result == expected

def test_MockLArPix_trigger():
    chip = MockLArPix(1, 0)
    result = chip.trigger(1e5, 3)
    expected_packet = Packet()
    expected_packet.chipid = 1
    expected_packet.channel_id = 3
    expected_packet.dataword = 39  # computed by hand
    expected_packet.timestamp = result['sent'].timestamp  # have to cheat
    expected_packet.assign_parity()
    expected = {'sent': expected_packet}
    assert result == expected

def test_MockSerial_write():
    serial = MockSerial()
    formatter = MockFormatter()
    serial.formatter = formatter
    chip = MockLArPix(0, 0)
    formatter.mosi_destination = chip
    chip.previous = formatter
    chip.next = formatter
    formatter.miso_source = chip
    packet = Packet()
    packet.assign_parity()
    bytestream = b's' + packet.bytes() + b'\x00q'
    serial.write(bytestream)
    result = formatter.miso_buffer
    expected = deque([packet])
    assert result == expected

def test_MockSerial_read_correct_nbytes():
    serial = MockSerial()
    formatter = MockFormatter()
    serial.formatter = formatter
    packet = Packet()
    formatter.miso_buffer.append(packet)
    result = serial.read(10)
    expected = b's' + packet.bytes() + b'\x00q'
    assert result == expected

def test_MockSerial_read_fewer_nbytes():
    serial = MockSerial()
    formatter = MockFormatter()
    serial.formatter = formatter
    packet = Packet()
    formatter.miso_buffer.append(packet)
    result = serial.read(5)
    expected = (b's' + packet.bytes() + b'\x00q')[:5]
    assert result == expected

def test_MockSerial_read_extra_nbytes():
    serial = MockSerial()
    formatter = MockFormatter()
    serial.formatter = formatter
    packet = Packet()
    formatter.miso_buffer.append(packet)
    result = serial.read(15)
    expected = b's' + packet.bytes() + b'\x00q'
    assert result == expected

def test_MockFormatter_receive_mosi():
    formatter = MockFormatter()
    chip = MockLArPix(0, 0)
    formatter.mosi_destination = chip
    chip.next = formatter
    packet = Packet()
    packet.assign_parity()
    bytestream = b's' + packet.bytes() + b'\x00q'
    formatter.receive_mosi(bytestream)
    result = formatter.miso_buffer
    expected = deque([packet])
    assert result == expected

def test_MockFormatter_receive_miso():
    formatter = MockFormatter()
    packet = Packet()
    formatter.receive_miso(packet)
    result = formatter.miso_buffer
    expected = deque([packet])
    assert result == expected

def test_MockFormatter_send_mosi():
    formatter = MockFormatter()
    chip = MockLArPix(0, 0)
    formatter.mosi_destination = chip
    chip.next = formatter
    packet = Packet()
    packet.assign_parity()
    formatter.send_mosi([packet])
    result = formatter.miso_buffer
    expected = deque([packet])
    assert result == expected

def test_MockFormatter_send_miso_full_packet():
    formatter = MockFormatter()
    packet = Packet()
    formatter.miso_buffer.append(packet)
    result = formatter.send_miso(10)
    expected = b's\x00\x00\x00\x00\x00\x00\x00\x00q'
    assert result == expected

def test_MockFormatter_send_miso_partial_packet():
    formatter = MockFormatter()
    packet = Packet()
    formatter.miso_buffer.append(packet)
    result = formatter.send_miso(5)
    expected = b's\x00\x00\x00\x00'
    assert result == expected
