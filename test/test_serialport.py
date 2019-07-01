'''
Tests for parsing and formatting for the SerialPort IO interface.

'''
from __future__ import print_function
import pytest
from larpix.io.serialport import SerialPort
from larpix.larpix import (Chip, Packet)

def test_serialport_format_UART(chip):
    packet = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)[10]
    result = SerialPort._format_UART(packet)
    expected = b'\x73' + packet.bytes() + b'\x00\x71'
    assert result == expected

def test_serialport_format_bytestream(chip):
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [SerialPort._format_UART(p) for p in packets]
    result = SerialPort.format_bytestream(fpackets[:1])
    assert result == fpackets[:1]
    result = SerialPort.format_bytestream(fpackets[:2])
    assert result == [b''.join(fpackets[:2])]
    test_total_packets = 2000
    result = SerialPort.format_bytestream(fpackets[:1]*test_total_packets)
    expected = []
    total_packets = test_total_packets
    while total_packets >= int(SerialPort.max_write/SerialPort.fpga_packet_size):
        expected.append(b''.join(fpackets[:1]*int(SerialPort.max_write/SerialPort.fpga_packet_size)))
        total_packets -= int(SerialPort.max_write/SerialPort.fpga_packet_size)
    if total_packets > 0:
        expected.append(b''.join(fpackets[:1]*int(total_packets)))
    assert result == expected

def test_serialport_parse_input(chip):
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [SerialPort._format_UART(p) for p in packets]
    bytestream = b''.join(SerialPort.format_bytestream(fpackets))
    result = SerialPort._parse_input(bytestream)
    expected = packets
    assert result == expected

def test_serialport_parse_input_dropped_data_byte(chip):
    # Test whether the parser can recover from dropped bytes
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [SerialPort._format_UART(p) for p in packets]
    bytestream = b''.join(SerialPort.format_bytestream(fpackets))
    # Drop a byte in the first packet
    bytestream_faulty = bytestream[:5] + bytestream[6:]
    result = SerialPort._parse_input(bytestream_faulty)
    #skipped = [(slice(0, 9), bytestream_faulty[0:9])]
    expected = packets[1:]
    assert result == expected

def test_serialport_parse_input_dropped_start_byte(chip):
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [SerialPort._format_UART(p) for p in packets]
    bytestream = b''.join(SerialPort.format_bytestream(fpackets))
    # Drop the first start byte
    bytestream_faulty = bytestream[1:]
    #skipped = [(slice(0, 9), bytestream_faulty[0:9])]
    result = SerialPort._parse_input(bytestream_faulty)
    expected = packets[1:]
    assert result == expected

def test_serialport_parse_input_dropped_stop_byte(chip):
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [SerialPort._format_UART(p) for p in packets]
    bytestream = b''.join(SerialPort.format_bytestream(fpackets))
    # Drop the first stop byte
    bytestream_faulty = bytestream[:9] + bytestream[10:]
    #skipped = [(slice(0, 9), bytestream_faulty[0:9])]
    result = SerialPort._parse_input(bytestream_faulty)
    expected = packets[1:]
    assert result == expected

def test_serialport_parse_input_dropped_stopstart_bytes(chip):
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [SerialPort._format_UART(p) for p in packets]
    bytestream = b''.join(SerialPort.format_bytestream(fpackets))
    # Drop the first stop byte
    bytestream_faulty = bytestream[:9] + bytestream[11:]
    #skipped = [(slice(0, 18), bytestream_faulty[:18])]
    result = SerialPort._parse_input(bytestream_faulty)
    expected = packets[2:]
    assert result == expected

