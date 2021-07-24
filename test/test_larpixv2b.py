'''
Use the pytest framework to write tests for the v2b upgrade to larpix chip.

'''
from __future__ import print_function
import pytest
from larpix import (Chip, Packet_v1, Packet_v2, Packet, Key, Configuration, Configuration_v1, Configuration_v2, Configuration_v2b, Controller,
        PacketCollection, _Smart_List, TimestampPacket, MessagePacket)
from larpix.io import FakeIO
#from bitstring import BitArray
from bitarray import bitarray
import larpix.bitarrayhelper as bah
import json
import os

import random



@pytest.fixture
def timestamp_packet():
    return TimestampPacket(123456789)

@pytest.fixture
def message_packet():
    return MessagePacket('test',123456789)

def list_of_packets_str(packets):
    return '\n'.join(map(str, packets)) + '\n'

def test_chip_str():
    key = '1-1-1'
    chip = Chip(key, version='2b')
    result = str(chip)
    expected = 'Chip (key: 1-1-1, version: 2b)'
    assert result == expected

def test_chip_get_configuration_packets(chip2b):
    packet_type = Packet.CONFIG_WRITE_PACKET
    packets = chip2b.get_configuration_write_packets()
    # test a sampling of the configuration packets
    packet = packets[5]
    assert packet.packet_type == packet_type
    assert packet.chip_id == chip2b.chip_id
    assert packet.register_address == 5
    assert packet.register_data == 16

    packet = packets[40]
    assert packet.packet_type == packet_type
    assert packet.chip_id == chip2b.chip_id
    assert packet.register_address == 40
    assert packet.register_data == 16

def test_chip_sync_configuration(chip2b):
    packet_type = Packet.CONFIG_READ_PACKET
    packets = chip2b.get_configuration_read_packets()
    chip2b.reads.append(PacketCollection(packets))
    chip2b.sync_configuration()
    result = chip2b.config.all_data()
    expected = [bitarray([0]*8)] * Configuration_v2b.num_registers
    assert result == expected

def test_chip_sync_configuration_slice(chip2b):
    packets = chip2b.get_configuration_read_packets()
    chip2b.reads.append(PacketCollection(packets[:10]))
    chip2b.reads.append(PacketCollection(packets[10:]))
    chip2b.sync_configuration(index=slice(None, None, None))
    result = chip2b.config.all_data()
    expected = [bitarray([0]*8)] * Configuration_v2b.num_registers
    assert result == expected

def test_chip_export_reads(chip2b):
    packet = Packet()
    packet.chip_key = chip2b.chip_key
    packet.packet_type = Packet.CONFIG_WRITE_PACKET
    packet.chip_id = chip2b.chip_id
    packet.register_address = 10
    packet.register_data = 20
    packet.assign_parity()
    chip2b.reads.append(packet)
    result = chip2b.export_reads()
    expected = {
            'chip_key': chip2b.chip_key,
            'chip_id': chip2b.chip_id,
            'packets': [
                packet.export()
                ]
            }
    assert result == expected
    assert chip2b.new_reads_index == 1

def test_configuration_write(tmpdir):
    c = Configuration_v2b()
    f = str(tmpdir.join('test_config.json'))
    c.write(f)
    with open(f, 'r') as output:
        result = json.load(output)
    expected = c.to_dict()
    assert result['register_values'] == expected

def test_configuration_write_errors(tmpdir):
    c = Configuration_v2b()
    f = tmpdir.join('test_config.json')
    f.write("Test data.....")
    with pytest.raises(IOError):
        c.write(str(f))
        pytest.fail('Should fail: force fails')

def test_controller_read_configuration(capfd, chip2b):
    controller = Controller()
    controller.io = FakeIO()
    controller.chips[chip2b.chip_key] = chip2b
    conf_data = chip2b.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    sent_expected = list_of_packets_str(conf_data)
    controller.io.queue.append((conf_data,b'hi'))
    received_expected = PacketCollection(conf_data, b'hi', read_id=0,
            message='configuration read')
    controller.read_configuration(chip2b.chip_key, timeout=0.01)
    received_result = controller.reads[-1]
    sent_result, err = capfd.readouterr()
    assert sent_result == sent_expected
    assert received_result == received_expected

def test_conf_v2b():
    c = Configuration_v2b()
    endian = 'little'

    # test simple register
    c.threshold_global = 255
    assert c.threshold_global == 255
    assert c.threshold_global_data == [(64, bah.fromuint(255,8, endian=endian))]

    c.threshold_global_data = (64, bah.fromuint(253,8, endian=endian))
    assert c.threshold_global == 253
    assert c.threshold_global_data == [(64, bah.fromuint(253,8, endian=endian))]

    c.threshold_global_data = bah.fromuint(252,8, endian=endian)
    assert c.threshold_global == 252
    assert c.threshold_global_data == [(64, bah.fromuint(252,8, endian=endian))]

    # test list register
    c.pixel_trim_dac = [0]*64
    assert c.pixel_trim_dac == [0]*64
    assert c.pixel_trim_dac_data == [(i, bah.fromuint(0,8, endian=endian)) for i in range(64)]

    c.pixel_trim_dac[1] = 1
    assert c.pixel_trim_dac[1] == 1
    assert c.pixel_trim_dac_data[1] == (1, bah.fromuint(1,8, endian=endian))
    assert c.pixel_trim_dac_data[0] == (0, bah.fromuint(0,8, endian=endian))

    c.pixel_trim_dac_data = (1, bah.fromuint(2,8, endian=endian))
    assert c.pixel_trim_dac[1] == 2
    assert c.pixel_trim_dac_data[1] == (1, bah.fromuint(2,8, endian=endian))
    assert c.pixel_trim_dac_data[0] == (0, bah.fromuint(0,8, endian=endian))

    bits = bitarray()
    for i in range(64):
        bits += bah.fromuint(31,8, endian=endian)
    c.pixel_trim_dac_data = bits
    assert c.pixel_trim_dac[1] == 31
    assert c.pixel_trim_dac[0] == 31
    assert c.pixel_trim_dac_data[1] == (1, bah.fromuint(31,8, endian=endian))
    assert c.pixel_trim_dac_data[0] == (0, bah.fromuint(31,8, endian=endian))

    # test compound register
    c.csa_gain = 1
    c.csa_bypass_enable = 1
    c.bypass_caps_en = 1
    reg_data = [(65, bitarray('11100000'))]
    assert c.csa_gain == 1
    assert c.csa_gain_data == reg_data
    assert c.csa_bypass_enable == 1
    assert c.csa_bypass_enable_data == reg_data
    assert c.bypass_caps_en == 1
    assert c.bypass_caps_en_data == reg_data

    c.csa_bypass_enable = 0
    reg_data = [(65, bitarray('10100000'))]
    assert c.csa_gain == 1
    assert c.csa_gain_data == reg_data
    assert c.csa_bypass_enable == 0
    assert c.csa_bypass_enable_data == reg_data
    assert c.bypass_caps_en == 1
    assert c.bypass_caps_en_data == reg_data

    reg_data = [(65, bitarray('01000000'))]
    c.csa_bypass_enable_data = reg_data[0]
    assert c.csa_gain == 0
    assert c.csa_gain_data == reg_data
    assert c.csa_bypass_enable == 1
    assert c.csa_bypass_enable_data == reg_data
    assert c.bypass_caps_en == 0
    assert c.bypass_caps_en_data == reg_data

    reg_data = [(65, bitarray('11000000'))]
    c.csa_gain_data = bitarray('1')
    assert c.csa_gain == 1
    assert c.csa_gain_data == reg_data
    assert c.csa_bypass_enable == 1
    assert c.csa_bypass_enable_data == reg_data
    assert c.bypass_caps_en == 0
    assert c.bypass_caps_en_data == reg_data

    # test list register (that covers <1 register)
    c.current_monitor_bank0 = [0]*4
    assert c.current_monitor_bank0 == [0]*4
    assert c.current_monitor_bank0_data == [(109, bah.fromuint(0,8, endian=endian))]

    c.current_monitor_bank0[1] = 1
    assert c.current_monitor_bank0[1] == 1
    assert c.current_monitor_bank0[0] == 0
    assert c.current_monitor_bank0_data == [(109, bitarray('01000000'))]

    c.current_monitor_bank0_data = (109, bitarray('00100000'))
    assert c.current_monitor_bank0[1] == 0
    assert c.current_monitor_bank0[2] == 1
    assert c.current_monitor_bank0_data == [(109, bitarray('00100000'))]

    bits = bitarray('0100')
    c.current_monitor_bank0_data = bits
    assert c.current_monitor_bank0[1] == 1
    assert c.current_monitor_bank0[0] == 0
    assert c.current_monitor_bank0_data == [(109, bitarray('01000000'))]

    # test long register
    c.periodic_trigger_cycles = 2**32-1
    assert c.periodic_trigger_cycles == 2**32-1
    assert c.periodic_trigger_cycles_data == [(i, bah.fromuint(255,8, endian=endian)) for i in range(166,170)]

    c.periodic_trigger_cycles_data = (166, bah.fromuint(254,8, endian=endian))
    assert c.periodic_trigger_cycles == 2**32-2
    assert c.periodic_trigger_cycles_data[0] == (166, bah.fromuint(254, 8, endian=endian))

    c.periodic_trigger_cycles_data = bah.fromuint(1,32, endian=endian)
    assert c.periodic_trigger_cycles == 1
    assert c.periodic_trigger_cycles_data[0] == (166, bah.fromuint(1,8, endian=endian))

    c.enable_piso_downstream[1] = 1
    assert c.enable_piso_downstream[1] == 1
    assert c.enable_piso_downstream[0] == 0
    assert c.enable_piso_downstream_data == [(125, bitarray('01000000'))]

    c.enable_piso_downstream_data = (125, bitarray('00100000'))
    assert c.enable_piso_downstream[1] == 0
    assert c.enable_piso_downstream[2] == 1
    assert c.enable_piso_downstream_data == [(125, bitarray('00100000'))]

    bits = bitarray('0100')
    c.enable_piso_downstream_data = bits
    assert c.enable_piso_downstream[1] == 1
    assert c.enable_piso_downstream[0] == 0
    assert c.enable_piso_downstream_data == [(125, bitarray('01000000'))]

    c.i_rx0 = 8
    c.i_rx1 = 1
    assert c.i_rx0_data == [(243, bitarray('00011000'))]
    assert c.i_rx1_data == [(243, bitarray('00011000'))]

    c.i_rx0 = 15
    assert c.i_rx0_data == [(243, bitarray('11111000'))]
    assert c.i_rx1_data == [(243, bitarray('11111000'))]

    c.test_mode_uart0 = 2
    c.test_mode_uart1 = 0
    c.test_mode_uart2 = 0
    c.test_mode_uart3 = 0

    assert c.test_mode_uart0_data == [(127, bitarray('01000000'))]

def test_compare_v2b():
    c = Configuration_v2b()
    other = Configuration_v2b()
    assert c.compare(other) == {}

    c.pixel_trim_dac[10] = 25
    c.pixel_trim_dac[12] = 26
    assert c.compare(other) == {'pixel_trim_dac': [
        ({'index': 10, 'value': 25}, {'index': 10, 'value': 16}),
        ({'index': 12, 'value': 26}, {'index': 12, 'value': 16}),
        ]}

    c = Configuration_v2b()
    c.threshold_global = 121
    assert c.compare(other) == {'threshold_global': (121, 255)}

def test_load_inheritance_v2b(tmpdir):
    filename = 'test.json'
    c = Configuration_v2b()
    with open(str(tmpdir.join(filename)),'w') as of:
        config = {
            "_config_type": "chip",
            "_include": ["chip/default_v2b.json"],
            "class": "Configuration_v2b",
            "register_values": {
                "pixel_trim_dac": [0, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16],
                "threshold_global": 0
            }
        }
        json.dump(config,of)
    c.load(str(tmpdir.join(filename)))
    assert c.pixel_trim_dac[0] == 0
    assert c.threshold_global == 0
    assert c.csa_gain == 0

def test_get_nondefault_registers_v2b():
    c = Configuration_v2b()
    c.pixel_trim_dac[10] = 25
    c.threshold_global = 121
    c.csa_gain = 1
    c.csa_enable[35] = 0
    assert c.get_nondefault_registers() == {
            'pixel_trim_dac': [({'index': 10, 'value': 25},
                {'index': 10, 'value': 16})],
            'threshold_global': (121, 255),
            'csa_gain': (1, 0),
            'csa_enable': [({'index': 35, 'value': 0}, {'index': 35,
                'value': 1})],
            }

def test_v2b_conf_all_data():
    c = Configuration_v2b()
    config_data = c.all_data()

    assert len(config_data) == c.num_registers, \
        f'config data length incorrect (should be {c.num_registers}, is {len(config_data)})'

    for reg_name in c.register_map.keys():
        reg_data = getattr(c, f'{reg_name}_data')
        for reg_addr, bits in reg_data:
            assert bits == config_data[reg_addr], \
                f'register {reg_addr} mismatch (should be {bits}, is {config_data[reg_addr]})'


def test_v2b_conf_some_data():
    c = Configuration_v2b()

    req_addrs = range(c.num_registers)
    addrs, bits = c.some_data(req_addrs)
    config_data = c.all_data()

    # check all addresses
    assert len(addrs) == len(req_addrs), \
        f'config data length incorrect (should be {len(req_addrs)}, is {len(addrs)})'
    assert set(addrs) == set(req_addrs), \
        f'config data values incorrect (should be {set(req_addrs)}, is {set(addrs)})'

    for addr, addr_bits in zip(addrs, bits):
        assert addr_bits == config_data[addr], \
            f'register {addr} mismatch (should be {config_data[addr]}, is {addr_bits})'

     # check partial addresses
    req_addrs = random.sample(range(c.num_registers), c.num_registers//2)
    addrs, bits = c.some_data(req_addrs)

    # check all addresses
    assert len(addrs) == len(req_addrs), \
        f'config data length incorrect (should be {len(req_addrs)}, is {len(addrs)})'
    assert set(addrs) == set(req_addrs), \
        f'config data values incorrect (should be {set(req_addrs)}, is {set(addrs)})'

    for addr, addr_bits in zip(addrs, bits):
        assert addr_bits == config_data[addr], \
            f'register {addr} mismatch (should be {config_data[addr]}, is {addr_bits})'

