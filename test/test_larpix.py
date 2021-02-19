'''
Use the pytest framework to write tests for the larpix module.

'''
from __future__ import print_function
import pytest
from larpix import (Chip, Packet_v1, Packet_v2, Packet, Key, Configuration, Configuration_v1, Controller,
        PacketCollection, _Smart_List, TimestampPacket, MessagePacket)
from larpix.io import FakeIO
#from bitstring import BitArray
from bitarray import bitarray
import larpix.bitarrayhelper as bah
import json
import os

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
    chip = Chip(key)
    result = str(chip)
    expected = 'Chip (key: 1-1-1, version: 2)'
    assert result == expected

def test_chip_get_configuration_packets(chip):
    packet_type = Packet.CONFIG_WRITE_PACKET
    packets = chip.get_configuration_write_packets()
    # test a sampling of the configuration packets
    packet = packets[5]
    assert packet.packet_type == packet_type
    assert packet.chip_id == chip.chip_id
    assert packet.register_address == 5
    assert packet.register_data == 16

    packet = packets[40]
    assert packet.packet_type == packet_type
    assert packet.chip_id == chip.chip_id
    assert packet.register_address == 40
    assert packet.register_data == 16

def test_chip_sync_configuration(chip):
    packet_type = Packet.CONFIG_READ_PACKET
    packets = chip.get_configuration_read_packets()
    chip.reads.append(PacketCollection(packets))
    chip.sync_configuration()
    result = chip.config.all_data()
    expected = [bitarray([0]*8)] * Configuration.num_registers
    assert result == expected

def test_chip_sync_configuration_slice(chip):
    packets = chip.get_configuration_read_packets()
    chip.reads.append(PacketCollection(packets[:10]))
    chip.reads.append(PacketCollection(packets[10:]))
    chip.sync_configuration(index=slice(None, None, None))
    result = chip.config.all_data()
    expected = [bitarray([0]*8)] * Configuration.num_registers
    assert result == expected

def test_chip_export_reads(chip):
    packet = Packet()
    packet.chip_key = chip.chip_key
    packet.packet_type = Packet.CONFIG_WRITE_PACKET
    packet.chip_id = chip.chip_id
    packet.register_address = 10
    packet.register_data = 20
    packet.assign_parity()
    chip.reads.append(packet)
    result = chip.export_reads()
    expected = {
            'chip_key': chip.chip_key,
            'chip_id': chip.chip_id,
            'packets': [
                packet.export()
                ]
            }
    assert result == expected
    assert chip.new_reads_index == 1

def test_chip_export_reads_no_new_reads(chip):
    result = chip.export_reads()
    expected = {'chip_id': chip.chip_id, 'chip_key': chip.chip_key, 'packets': []}
    assert result == expected
    assert chip.new_reads_index == 0
    packet = Packet()
    packet.packet_type = Packet.CONFIG_WRITE_PACKET
    chip.reads.append(packet)
    chip.export_reads()
    result = chip.export_reads()
    assert result == expected
    assert chip.new_reads_index == 1

def test_chip_export_reads_all(chip):
    packet = Packet()
    packet.chip_key = chip.chip_key
    packet.chipid = chip.chip_id
    packet.packet_type = Packet.CONFIG_WRITE_PACKET
    chip.reads.append(packet)
    chip.export_reads()
    result = chip.export_reads(only_new_reads=False)
    expected = {
            'chip_id': chip.chip_id,
            'chip_key': chip.chip_key,
            'packets': [
                packet.export()
                ]
            }
    assert result == expected
    assert chip.new_reads_index == 1

def test_controller_save_output(tmpdir, chip):
    controller = Controller()
    p = Packet()
    controller.add_chip(chip.chip_key)
    collection = PacketCollection([p], p.bytes(), 'hi', 0)
    controller.reads.append(collection)
    name = str(tmpdir.join('test.json'))
    controller.save_output(name, 'this is a test')
    with open(name) as f:
        result = json.load(f)
    expected = {
            'chips': [repr(chip)],
            'message': 'this is a test',
            'reads': [
                collection.to_dict()
                ]
            }
    assert result == expected

def test_packet_bits_bytes():
    assert Packet.num_bytes == Packet.size // 8 + min(Packet.size % 8, 1)

def test_packet_init_default():
    p = Packet()
    expected = bitarray([0] * Packet.size)
    assert p.bits == expected

def test_packet_init_bytestream():
    bytestream = b'\x3f' + b'\x00' * (Packet.num_bytes-2) + b'\xf8'
    p = Packet(bytestream)
    if isinstance(p, Packet_v1):
        expected = bitarray([0] * Packet.size)
        expected[-6:] = bitarray([1]*6)
        expected[:5] = bitarray([1]*5)
        print(expected[0],expected[-1])
        assert p.bits == expected
    else:
        expected = bitarray([0] * Packet.size)
        expected[:6] = bitarray([1]*6)
        expected[-5:] = bitarray([1]*5)
        print(expected[0],expected[-1])
        assert p.bits == expected

def test_packet_bytes_zeros():
    p = Packet()
    b = p.bytes()
    expected = b'\x00' * Packet.num_bytes
    assert b == expected

def test_packet_bytes_custom():
    p = Packet()
    p.bits[-6:] = bitarray([1]*6)
    p.bits[:7] = bitarray([0]*2+[1]*5)
    b = p.bytes()
    if isinstance(p, Packet_v1):
        expected = b'\x3f' + b'\x00' * (Packet.num_bytes-2) + b'\x3e'
        assert b == expected
    else:
        expected = b'\x7c' + b'\x00' * (Packet.num_bytes-2) + b'\xfc'
        assert b == expected

def test_packet_v1_bytes_properties():
    p = Packet_v1()
    p.packet_type = Packet_v1.DATA_PACKET
    p.chipid = 100
    expected = b'\x90\x01' + b'\x00' * (Packet_v1.num_bytes-2)
    b = p.bytes()
    assert b == expected

def test_packet_v1_export_test():
    p = Packet_v1()
    p.packet_type = Packet_v1.TEST_PACKET
    p.chipid = 5
    p.test_counter = 32838
    p.assign_parity()
    result = p.export()
    expected = {
            'asic_version': 1,
            'bits': p.bits.to01(),
            'type_str': 'test',
            'type': 1,
            'chipid': 5,
            'chip_key': None,
            'counter': 32838,
            'parity': p.parity_bit_value,
            'valid_parity': True,
            }
    assert result == expected

def test_packet_v1_export_data():
    p = Packet_v1()
    p.packet_type = Packet_v1.DATA_PACKET
    p.chipid = 2
    p.chip_key = Key('1-3-2')
    p.channel_id = 10
    p.timestamp = 123456
    p.dataword = 180
    p.fifo_half_flag = True
    p.fifo_full_flag = False
    p.assign_parity()
    result = p.export()
    expected = {
            'asic_version': 1,
            'bits': p.bits.to01(),
            'type_str': 'data',
            'type': 0,
            'chipid': 2,
            'chip_key': p.chip_key,
            'channel': 10,
            'timestamp': 123456,
            'adc_counts': 180,
            'fifo_half': True,
            'fifo_full': False,
            'parity': p.parity_bit_value,
            'valid_parity': True,
            }
    assert result == expected

def test_packet_v1_export_config_read():
    p = Packet_v1()
    p.packet_type = Packet_v1.CONFIG_READ_PACKET
    p.chipid = 10
    p.chip_key = Key('2-1-10')
    p.register_address = 51
    p.register_data = 2
    p.assign_parity()
    result = p.export()
    expected = {
            'asic_version': 1,
            'bits': p.bits.to01(),
            'type_str': 'config read',
            'type': 3,
            'chipid': 10,
            'chip_key': p.chip_key,
            'register': 51,
            'value': 2,
            'parity': p.parity_bit_value,
            'valid_parity': True,
            }
    assert result == expected

def test_packet_v1_export_config_write():
    p = Packet_v1()
    p.packet_type = Packet_v1.CONFIG_WRITE_PACKET
    p.chipid = 10
    p.register_address = 51
    p.register_data = 2
    p.assign_parity()
    result = p.export()
    expected = {
            'asic_version': 1,
            'bits': p.bits.to01(),
            'type_str': 'config write',
            'type': 2,
            'chipid': 10,
            'chip_key': p.chip_key,
            'register': 51,
            'value': 2,
            'parity': p.parity_bit_value,
            'valid_parity': True,
            }
    assert result == expected

def test_packet_v1_from_dict():
    p = Packet_v1()
    p1 = Packet_v1()
    p.packet_type = Packet_v1.CONFIG_WRITE_PACKET
    p.chipid = 10
    p.register_address = 51
    p.register_data = 2
    p.assign_parity()
    packet_dict = {
            'asic_version': 1,
            'bits': p.bits.to01(),
            'type_str': 'config write',
            'type': 2,
            'chipid': 10,
            'chip_key': None,
            'register': 51,
            'value': 2,
            'parity': p.parity_bit_value,
            'valid_parity': True,
            }
    p1.from_dict(packet_dict)
    assert p == p1

def test_packet_v1_from_dict_export_inv():
    p = Packet_v1()
    p1 = Packet_v1()
    p.packet_type = Packet_v1.CONFIG_WRITE_PACKET
    p.chipid = 10
    p.register_address = 51
    p.register_data = 2
    p.assign_parity()
    packet_dict = p.export()
    p1.from_dict(packet_dict)
    assert p == p1

def test_packet_v1_set_packet_type():
    p = Packet_v1()
    p.packet_type = Packet_v1.DATA_PACKET
    packet_bits = p.bits[Packet.packet_type_bits]
    expected = Packet_v1.DATA_PACKET
    assert packet_bits == expected

def test_packet_get_packet_type():
    p = Packet()
    p.packet_type = Packet.CONFIG_WRITE_PACKET
    packet_type = p.packet_type
    expected = Packet.CONFIG_WRITE_PACKET
    assert packet_type == expected

def test_packet_v1_set_chipid():
    p = Packet_v1()
    p.chipid = 121
    expected = bah.fromuint(121, 8)
    assert p.bits[Packet_v1.chipid_bits] == expected

def test_packet_get_chipid():
    p = Packet()
    p.chipid = 18
    expected = 18
    assert p.chipid == expected

def test_packet_v1_set_parity_bit_value():
    p = Packet_v1()
    p.parity_bit_value = 0
    assert p.bits[0] == False
    p.parity_bit_value = 1
    assert p.bits[0] == True

def test_packet_get_parity_bit_value():
    p = Packet()
    p.parity_bit_value = 0
    assert p.parity_bit_value == 0
    p.parity_bit_value = 1
    assert p.parity_bit_value == 1

def test_packet_v1_compute_parity():
    p = Packet_v1()
    p.chipid = 121
    parity = p.compute_parity()
    expected = 0
    assert parity == expected
    p.bits = bitarray([0]*54)
    parity = p.compute_parity()
    expected = 1
    assert parity == expected
    p.bits = bitarray([1]*54)
    parity = p.compute_parity()
    expected = 0
    assert parity == expected

def test_packet_v1_assign_parity():
    p = Packet_v1()
    p.chipid = 121
    p.assign_parity()
    expected = 0
    assert p.parity_bit_value == expected
    p.chipid = 0
    p.assign_parity()
    expected = 1
    assert p.parity_bit_value == expected

def test_packet_v1_has_valid_parity():
    p = Packet_v1()
    result = p.has_valid_parity()
    expected = False
    assert result == expected
    p.assign_parity()
    result = p.has_valid_parity()
    expected = True
    assert result == expected
    p.bits = bitarray([1]*54)
    result = p.has_valid_parity()
    expected = False
    assert result == expected
    p.assign_parity()
    result = p.has_valid_parity()
    expected = True
    assert result == expected

def test_packet_v1_set_channel_id():
    p = Packet_v1()
    p.channel_id = 100
    expected = bah.fromuint(100, 7)
    assert p.bits[Packet_v1.channel_id_bits] == expected

def test_packet_v1_get_channel_id():
    p = Packet_v1()
    expected = 101
    p.channel_id = expected
    assert p.channel_id == expected

def test_packet_v1_set_timestamp():
    p = Packet_v1()
    p.timestamp = 0x1327ab
    expected = bah.fromuint(int('0x1327ab', 16), 24)
    assert p.bits[Packet_v1.timestamp_bits] == expected

def test_packet_get_timestamp():
    p = Packet()
    expected = 0xa82b6e
    p.timestamp = expected
    assert p.timestamp == expected

def test_packet_v1_set_dataword():
    p = Packet_v1()
    p.dataword = 75
    expected = bah.fromuint(75, 10)
    assert p.bits[Packet_v1.dataword_bits] == expected

def test_packet_get_dataword():
    p = Packet()
    expected = 74
    p.dataword = 74
    assert p.dataword == expected

def test_packet_v1_get_dataword_ADC_bug():
    p = Packet_v1()
    expected = 74
    p.dataword = 75
    assert p.dataword == expected

def test_packet_v1_set_fifo_half_flag():
    p = Packet_v1()
    p.fifo_half_flag = 1
    expected = True
    assert p.bits[Packet_v1.fifo_half_bit] == expected

def test_packet_v1_get_fifo_half_flag():
    p = Packet_v1()
    expected = 1
    p.fifo_half_flag = expected
    assert p.fifo_half_flag == expected

def test_packet_v1_set_fifo_full_flag():
    p = Packet_v1()
    p.fifo_full_flag = 1
    expected = True
    assert p.bits[Packet_v1.fifo_full_bit] == expected

def test_packet_v1_get_fifo_full_flag():
    p = Packet_v1()
    expected = 1
    p.fifo_full_flag = expected
    assert p.fifo_full_flag == expected

def test_packet_set_register_address():
    p = Packet()
    p.register_address = 121
    if isinstance(p,Packet_v1):
        expected = bah.fromuint(121, 8)
    else:
        expected = bah.fromuint(121, 8, endian=p.endian)
    assert p.bits[Packet.register_address_bits] == expected

def test_packet_get_register_address():
    p = Packet()
    p.register_address = 18
    expected = 18
    assert p.register_address == expected

def test_packet_set_register_data():
    p = Packet()
    p.register_data = 1
    if isinstance(p,Packet_v1):
        expected = bah.fromuint(1, 8)
    else:
        expected = bah.fromuint(1, 8, endian=p.endian)
    assert p.bits[Packet.register_data_bits] == expected

def test_packet_get_register_data():
    p = Packet()
    p.register_data = 18
    expected = 18
    assert p.register_data == expected

def test_packet_v1_set_test_counter():
    p = Packet_v1()
    p.test_counter = 18376
    expected = bah.fromuint(18376, 16)
    result = (p.bits[Packet_v1.test_counter_bits_15_12] +
            p.bits[Packet_v1.test_counter_bits_11_0])
    assert result == expected

def test_packet_get_test_counter():
    p = Packet()
    expected = 19831
    p.test_counter = expected
    assert p.test_counter == expected

def test_configuration_error_on_unknown_field():
    c = Configuration()
    with pytest.raises(AttributeError):
        c.this_is_a_dummy_attr = 0
        pytest.fail('Should fail: attribute is not in known '
                       'register names')

def test_configuration_v1_no_error_on_known_register_name():
    c = Configuration_v1()
    c.reset_cycles = 5

def test_configuration_no_error_on_underscore():
    c = Configuration()
    c._underscore = 'hello'

def test_configuration_no_error_on_hasattr():
    c = Configuration()
    c.num_registers = 0

def test_configuration_get_nondefault_registers():
    c = Configuration()
    expected = {}
    assert c.get_nondefault_registers() == expected
    c.adc_burst_length += 1
    expected['adc_burst_length'] = (c.adc_burst_length, c.adc_burst_length-1)
    assert c.get_nondefault_registers() == expected

def test_configuration_get_nondefault_registers_array():
    c = Configuration()
    default = c.channel_mask[1]
    c.channel_mask[1] = int(not c.channel_mask[1])
    c.channel_mask[5] = int(not c.channel_mask[5])
    result = c.get_nondefault_registers()
    print(c.channel_mask)
    expected = {
            'channel_mask': [
                ({'index': 1, 'value': c.channel_mask[1]}, {'index': 1, 'value': default}),
                ({'index': 5, 'value': c.channel_mask[5]}, {'index': 5, 'value': default})
                ]
            }
    assert result == expected

def test_configuration_get_nondefault_registers_many_changes():
    c = Configuration()
    default = list(c.channel_mask)
    c.channel_mask[:20] = list(map(lambda x: not x, c.channel_mask[:20]))
    result = c.get_nondefault_registers()
    expected = { 'channel_mask': (c.channel_mask, default) }
    assert result == expected


def test_configuration_v1_set_pixel_trim_thresholds():
    c = Configuration_v1()
    expected = [0x05] * Configuration_v1.num_channels
    c.pixel_trim_thresholds = expected
    assert c._pixel_trim_thresholds == expected
    expected[5] = 0x10
    c.pixel_trim_thresholds[5] = 0x10
    assert c._pixel_trim_thresholds == expected

def test_configuration_v1_set_pixel_trim_thresholds_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.pixel_trim_thresholds = [0x05] * (Configuration_v1.num_channels-1)
        pytest.fail(message='Should fail: wrong num_channels')
    with pytest.raises(ValueError):
        c.pixel_trim_thresholds = [0x20] * Configuration_v1.num_channels
        pytest.fail(message='Should fail: values too large')
    with pytest.raises(ValueError,):
        c.pixel_trim_thresholds = [-10] * Configuration_v1.num_channels
        pytest.fail(message='Should fail: value negative')
    with pytest.raises(ValueError):
        c.pixel_trim_thresholds = 5
        pytest.fail(message='Should fail: wrong type')

def test_configuration_v1_get_pixel_trim_thresholds():
    c = Configuration_v1()
    expected = [0x10] * Configuration_v1.num_channels
    c._pixel_trim_thresholds = expected
    assert c.pixel_trim_thresholds == expected

def test_configuration_v1_set_global_threshold():
    c = Configuration_v1()
    expected = 0x5a
    c.global_threshold = expected
    assert c._global_threshold == expected

def test_configuration_v1_set_global_threshold_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.global_threshold = 0x100
        pytest.fail(message='Should fail: values too large')
    with pytest.raises(ValueError):
        c.global_threshold = -10
        pytest.fail(message='Should fail: value negative')
    with pytest.raises(ValueError):
        c.global_threshold = True
        pytest.fail(message='Should fail: wrong type')

def test_configuration_v1_get_global_threshold():
    c = Configuration_v1()
    expected = 0x50
    c._global_threshold = expected
    assert c.global_threshold == expected

def test_configuration_v1_set_csa_gain():
    c = Configuration_v1()
    expected = 0
    c.csa_gain = expected
    assert c._csa_gain == expected

def test_configuration_v1_set_csa_gain_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.csa_gain = 5
        pytest.fail('Should fail: invalid value')
    with pytest.raises(ValueError):
        c.csa_gain = False
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_csa_gain():
    c = Configuration_v1()
    expected = 0
    c._csa_gain = expected
    assert c.csa_gain == expected

def test_configuration_v1_set_csa_bypass():
    c = Configuration_v1()
    expected = 0
    c.csa_bypass = expected
    assert c._csa_bypass == expected

def test_configuration_v1_set_csa_bypass_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.csa_bypass = 5
        pytest.fail('Should fail: invalid value')
    with pytest.raises(ValueError):
        c.csa_bypass = False
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_csa_bypass():
    c = Configuration_v1()
    expected = 0
    c._csa_bypass = expected
    assert c.csa_bypass == expected

def test_configuration_v1_set_internal_bypass():
    c = Configuration_v1()
    expected = 0
    c.internal_bypass = expected
    assert c._internal_bypass == expected

def test_configuration_v1_set_internal_bypass_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.internal_bypass = 5
        pytest.fail('Should fail: invalid value')
    with pytest.raises(ValueError):
        c.internal_bypass = False
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_internal_bypass():
    c = Configuration_v1()
    expected = 0
    c._internal_bypass = expected
    assert c.internal_bypass == expected

def test_configuration_v1_set_csa_bypass_select():
    c = Configuration_v1()
    expected = [0x1] * Configuration_v1.num_channels
    c.csa_bypass_select = expected
    assert c._csa_bypass_select == expected
    expected[5] = 0x0
    c.csa_bypass_select[5] = expected[5]
    assert c._csa_bypass_select == expected

def test_configuration_v1_set_csa_bypass_select_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.csa_bypass_select = [0x1] * (Configuration_v1.num_channels-1)
        pytest.fail('Should fail: wrong num_channels')
    with pytest.raises(ValueError):
        c.csa_bypass_select = [0x2] * Configuration_v1.num_channels
        pytest.fail('Should fail: value too large')
    with pytest.raises(ValueError):
        c.csa_bypass_select = [-1] * Configuration_v1.num_channels
        pytest.fail('Should fail: value negative')
    with pytest.raises(ValueError):
        c.csa_bypass_select = 5
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_csa_bypass_select():
    c = Configuration_v1()
    expected = [0x1] * Configuration_v1.num_channels
    c._csa_bypass_select = expected
    assert c.csa_bypass_select == expected

def test_configuration_v1_set_csa_monitor_select():
    c = Configuration_v1()
    expected = [0x0] * Configuration_v1.num_channels
    c.csa_monitor_select = expected
    assert c._csa_monitor_select == expected
    expected[5] = 0x1
    c.csa_monitor_select[5] = expected[5]
    assert c._csa_monitor_select == expected

def test_configuration_v1_set_csa_monitor_select_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.csa_monitor_select = [0x1] * (Configuration_v1.num_channels-1)
        pytest.fail('Should fail: wrong num_channels')
    with pytest.raises(ValueError):
        c.csa_monitor_select = [0x2] * Configuration_v1.num_channels
        pytest.fail('Should fail: value too lare')
    with pytest.raises(ValueError):
        c.csa_monitor_select = [-1] * Configuration_v1.num_channels
        pytest.fail('Should fail: value negative')
    with pytest.raises(ValueError):
        c.csa_monitor_select = 5
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_csa_monitor_select():
    c = Configuration_v1()
    expected = [0x0] * Configuration_v1.num_channels
    c._csa_monitor_select = expected
    assert c.csa_monitor_select == expected

def test_configuration_v1_set_csa_testpulse_enable():
    c = Configuration_v1()
    expected = [0x1] * Configuration_v1.num_channels
    c.csa_testpulse_enable = expected
    assert c._csa_testpulse_enable == expected
    expected[5] = 0x0
    c.csa_testpulse_enable[5] = expected[5]
    assert c._csa_testpulse_enable == expected

def test_configuration_v1_set_csa_testpulse_enable_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.csa_testpulse_enable = [0x1] * (Configuration_v1.num_channels-1)
        pytest.fail('Should fail: wrong num_channels')
    with pytest.raises(ValueError):
        c.csa_testpulse_enable = [0x2] * Configuration_v1.num_channels
        pytest.fail('Should fail: value too large')
    with pytest.raises(ValueError):
        c.csa_testpulse_enable = [-1] * Configuration_v1.num_channels
        pytest.fail('Should fail: value negative')
    with pytest.raises(ValueError):
        c.csa_testpulse_enable = 5
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_csa_testpulse_enable():
    c = Configuration_v1()
    expected = [0x1] * Configuration_v1.num_channels
    c._csa_testpulse_enable = expected
    assert c.csa_testpulse_enable == expected

def test_configuration_v1_set_csa_testpulse_dac_amplitude():
    c = Configuration_v1()
    expected = 0x5a
    c.csa_testpulse_dac_amplitude = expected
    assert c._csa_testpulse_dac_amplitude == expected

def test_configuration_v1_set_csa_testpulse_dac_amplitude_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.csa_testpulse_dac_amplitude = 0x100
        pytest.fail('Should fail: value too large')
    with pytest.raises(ValueError):
        c.csa_testpulse_dac_amplitude = -10
        pytest.fail('Should fail: value negative')
    with pytest.raises(ValueError):
        c.csa_testpulse_dac_amplitude = True
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_csa_testpulse_dac_amplitude():
    c = Configuration_v1()
    expected = 0x50
    c._csa_testpulse_dac_amplitude = expected
    assert c.csa_testpulse_dac_amplitude == expected

def test_configuration_v1_set_test_mode():
    c = Configuration_v1()
    expected = Configuration_v1.TEST_UART
    c.test_mode = expected
    assert c._test_mode == expected

def test_configuration_v1_set_test_mode_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.test_mode = 5
        pytest.fail('Should fail: invalid value')
    with pytest.raises(ValueError):
        c.test_mode = False
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_test_mode():
    c = Configuration_v1()
    expected = Configuration_v1.TEST_FIFO
    c._test_mode = expected
    assert c.test_mode == expected

def test_configuration_v1_set_cross_trigger_mode():
    c = Configuration_v1()
    expected = 0
    c.cross_trigger_mode = expected
    assert c._cross_trigger_mode == expected

def test_configuration_v1_set_cross_trigger_mode_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.cross_trigger_mode = 5
        pytest.fail('Should fail: invalid value')
    with pytest.raises(ValueError):
        c.cross_trigger_mode = False
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_cross_trigger_mode():
    c = Configuration_v1()
    expected = 0
    c._cross_trigger_mode = expected
    assert c.cross_trigger_mode == expected

def test_configuration_v1_set_periodic_reset():
    c = Configuration_v1()
    expected = 0
    c.periodic_reset = expected
    assert c._periodic_reset == expected

def test_configuration_v1_set_periodic_reset_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.periodic_reset = 5
        pytest.fail('Should fail: invalid value')
    with pytest.raises(ValueError):
        c.periodic_reset = False
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_periodic_reset():
    c = Configuration_v1()
    expected = 0
    c._periodic_reset = expected
    assert c.periodic_reset == expected

def test_configuration_v1_set_fifo_diagnostic():
    c = Configuration_v1()
    expected = 0
    c.fifo_diagnostic = expected
    assert c._fifo_diagnostic == expected

def test_configuration_v1_set_fifo_diagnostic_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.fifo_diagnostic = 5
        pytest.fail('Should fail: invalid value')
    with pytest.raises(ValueError):
        c.fifo_diagnostic = False
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_fifo_diagnostic():
    c = Configuration_v1()
    expected = 0
    c._fifo_diagnostic = expected
    assert c.fifo_diagnostic == expected

def test_configuration_v1_set_test_burst_length():
    c = Configuration_v1()
    expected = 0x125a
    c.test_burst_length = expected
    assert c._test_burst_length == expected

def test_configuration_v1_set_test_burst_length_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.test_burst_length = 0x10000
        pytest.fail('Should fail: value too large')
    with pytest.raises(ValueError):
        c.test_burst_length = -10
        pytest.fail('Should fail: value negative')
    with pytest.raises(ValueError):
        c.test_burst_length = True
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_test_burst_length():
    c = Configuration_v1()
    expected = 0x502e
    c._test_burst_length = expected
    assert c.test_burst_length == expected

def test_configuration_v1_set_adc_burst_length():
    c = Configuration_v1()
    expected = 0x5a
    c.adc_burst_length = expected
    assert c._adc_burst_length == expected

def test_configuration_v1_set_adc_burst_length_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.adc_burst_length = 0x100
        pytest.fail('Should fail: value too large')
    with pytest.raises(ValueError):
        c.adc_burst_length = -10
        pytest.fail('Should fail: value negative')
    with pytest.raises(ValueError):
        c.adc_burst_length = True
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_adc_burst_length():
    c = Configuration_v1()
    expected = 0x50
    c._adc_burst_length = expected
    assert c.adc_burst_length == expected

def test_configuration_v1_set_channel_mask():
    c = Configuration_v1()
    expected = [0x1] * Configuration_v1.num_channels
    c.channel_mask = expected
    assert c._channel_mask == expected
    expected[5] = 0x0
    c.channel_mask[5] = expected[5]
    assert c._channel_mask == expected

def test_configuration_v1_set_channel_mask_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.channel_mask = [0x1] * (Configuration_v1.num_channels-1)
        pytest.fail('Should fail: wrong num_channels')
    with pytest.raises(ValueError):
        c.channel_mask = [0x2] * Configuration_v1.num_channels
        pytest.fail('Should fail: value too large')
    with pytest.raises(ValueError):
        c.channel_mask = [-1] * Configuration_v1.num_channels
        pytest.fail('Should fail: value negative')
    with pytest.raises(ValueError):
        c.channel_mask = 5
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_channel_mask():
    c = Configuration_v1()
    expected = [0x1] * Configuration_v1.num_channels
    c._channel_mask = expected
    assert c.channel_mask == expected

def test_configuration_v1_set_external_trigger_mask():
    c = Configuration_v1()
    expected = [0x0] * Configuration_v1.num_channels
    c.external_trigger_mask = expected
    assert c._external_trigger_mask == expected
    expected[5] = 0x1
    c.external_trigger_mask[5] = expected[5]
    assert c._external_trigger_mask == expected

def test_configuration_v1_set_external_trigger_mask_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.external_trigger_mask = [0x1] * (Configuration_v1.num_channels-1)
        pytest.fail('Should fail: wrong num_channels')
    with pytest.raises(ValueError):
        c.external_trigger_mask = [0x2] * Configuration_v1.num_channels
        pytest.fail('Should fail: value too large')
    with pytest.raises(ValueError):
        c.external_trigger_mask = [-1] * Configuration_v1.num_channels
        pytest.fail('Should fail: value negative')
    with pytest.raises(ValueError):
        c.external_trigger_mask = 5
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_external_trigger_mask():
    c = Configuration_v1()
    expected = [0x0] * Configuration_v1.num_channels
    c._external_trigger_mask = expected
    assert c.external_trigger_mask == expected

def test_configuration_v1_set_reset_cycles():
    c = Configuration_v1()
    expected = 0x125abc
    c.reset_cycles = expected
    assert c._reset_cycles == expected

def test_configuration_v1_set_reset_cycles_errors():
    c = Configuration_v1()
    with pytest.raises(ValueError):
        c.reset_cycles = 0x1000000
        pytest.fail('Should fail: value too large')
    with pytest.raises(ValueError):
        c.reset_cycles = -10
        pytest.fail('Should fail: value negative')
    with pytest.raises(ValueError):
        c.reset_cycles = True
        pytest.fail('Should fail: wrong type')

def test_configuration_v1_get_reset_cycles():
    c = Configuration_v1()
    expected = 0x502ef2
    c._reset_cycles = expected
    assert c.reset_cycles == expected

def test_configuration_v1_disable_channels():
    c = Configuration_v1()
    expected = [0, 1] * 16
    c.disable_channels(range(1, 32, 2))
    assert c.channel_mask == expected

def test_configuration_v1_disable_channels_default():
    c = Configuration_v1()
    expected = [1] * 32
    c.disable_channels()
    assert c.channel_mask == expected

def test_configuration_v1_enable_channels():
    c = Configuration_v1()
    expected = [0, 1] * 16
    c.disable_channels()
    c.enable_channels(range(0, 32, 2))
    assert c.channel_mask == expected

def test_configuration_v1_enable_channels_default():
    c = Configuration_v1()
    expected = [0] * 32
    c.disable_channels()
    c.enable_channels()
    assert c.channel_mask == expected

def test_configuration_v1_enable_external_trigger():
    c = Configuration_v1()
    expected = [0, 1] * 16
    c.enable_external_trigger(range(0, 32, 2))
    assert c.external_trigger_mask == expected

def test_configuration_v1_enable_external_trigger_default():
    c = Configuration_v1()
    expected = [0] * 32
    c.enable_external_trigger()
    assert c.external_trigger_mask == expected

def test_configuration_v1_disable_external_trigger():
    c = Configuration_v1()
    expected = [0, 1] * 16
    c.enable_external_trigger()
    c.disable_external_trigger(range(1, 32, 2))
    assert c.external_trigger_mask == expected

def test_configuration_v1_enable_testpulse():
    c = Configuration_v1()
    expected = [1, 0] * 16
    c.disable_testpulse()
    c.enable_testpulse(range(1, 32, 2))
    assert c.csa_testpulse_enable == expected

def test_configuration_v1_enable_testpulse_default():
    c = Configuration_v1()
    expected = [0] * 32
    c.enable_testpulse()
    assert c.csa_testpulse_enable == expected

def test_configuration_v1_disable_testpulse():
    c = Configuration_v1()
    expected = [1, 0] * 16
    c.enable_testpulse()
    c.disable_testpulse(range(0, 32, 2))
    assert c.csa_testpulse_enable == expected

def test_configuration_v1_disable_testpulse_default():
    c = Configuration_v1()
    expected = [1] * 32
    c.disable_testpulse()
    assert c.csa_testpulse_enable == expected

def test_configuration_v1_enable_analog_monitor():
    c = Configuration_v1()
    expected = [0, 0, 1] + [0] * 29
    c.enable_analog_monitor(2)
    assert c.csa_monitor_select == expected

def test_configuration_v1_disable_analog_monitor():
    c = Configuration_v1()
    expected = [0] * 32
    c.enable_analog_monitor(5)
    c.disable_analog_monitor()
    assert c.csa_monitor_select == expected

def test_configuration_v1_trim_threshold_data():
    c = Configuration_v1()
    expected = bah.fromuint(int('0x10', 16), 8)
    assert c.trim_threshold_data(0) == expected

def test_configuration_v1_global_threshold_data():
    c = Configuration_v1()
    expected = bah.fromuint(int('0x10', 16), 8)
    assert c.global_threshold_data() == expected

def test_configuration_v1_csa_gain_and_bypasses_data():
    c = Configuration_v1()
    expected = bitarray('00000001')
    assert c.csa_gain_and_bypasses_data() == expected

def test_configuration_v1_csa_bypass_select_data():
    c = Configuration_v1()
    c.csa_bypass_select[4] = 1
    expected = bitarray('00010000')
    assert c.csa_bypass_select_data(0) == expected
    c.csa_bypass_select[10] = 1
    expected = bitarray('00000100')
    assert c.csa_bypass_select_data(1) == expected
    c.csa_bypass_select[20] = 1
    expected = bitarray('00010000')
    assert c.csa_bypass_select_data(2) == expected
    c.csa_bypass_select[30] = 1
    expected = bitarray('01000000')
    assert c.csa_bypass_select_data(3) == expected

def test_configuration_v1_csa_monitor_select_data():
    c = Configuration_v1()
    c.csa_monitor_select[4] = 1
    expected = bitarray('00010000')
    assert c.csa_monitor_select_data(0) == expected
    c.csa_monitor_select[10] = 1
    expected = bitarray('00000100')
    assert c.csa_monitor_select_data(1) == expected
    c.csa_monitor_select[20] = 1
    expected = bitarray('00010000')
    assert c.csa_monitor_select_data(2) == expected
    c.csa_monitor_select[30] = 1
    expected = bitarray('01000000')
    assert c.csa_monitor_select_data(3) == expected

def test_configuration_v1_csa_testpulse_enable_data():
    c = Configuration_v1()
    c.csa_testpulse_enable[4] = 0
    expected = bitarray('11101111')
    assert c.csa_testpulse_enable_data(0) == expected
    c.csa_testpulse_enable[10] = 0
    expected = bitarray('11111011')
    assert c.csa_testpulse_enable_data(1) == expected
    c.csa_testpulse_enable[20] = 0
    expected = bitarray('11101111')
    assert c.csa_testpulse_enable_data(2) == expected
    c.csa_testpulse_enable[30] = 0
    expected = bitarray('10111111')
    assert c.csa_testpulse_enable_data(3) == expected

def test_configuration_v1_csa_testpulse_dac_amplitude_data():
    c = Configuration_v1()
    c.csa_testpulse_dac_amplitude = 200;
    expected = bitarray('11001000')
    assert c.csa_testpulse_dac_amplitude_data() == expected

def test_configuration_v1_test_mode_xtrig_reset_diag_data():
    c = Configuration_v1()
    c.test_mode = 2
    c.fifo_diagnostic = 1
    expected = bitarray('00010010')
    assert c.test_mode_xtrig_reset_diag_data() == expected

def test_configuration_v1_sample_cycles_data():
    c = Configuration_v1()
    c.sample_cycles = 221
    expected = bitarray('11011101')
    assert c.sample_cycles_data() == expected

def test_configuration_v1_test_burst_length_data():
    c = Configuration_v1()
    expected = bah.fromuint(int('0xFF', 16), 8)
    assert c.test_burst_length_data(0) == expected
    expected = bah.fromuint(int('0x00', 16), 8)
    assert c.test_burst_length_data(1) == expected

def test_configuration_v1_adc_burst_length_data():
    c = Configuration_v1()
    c.adc_burst_length = 140
    expected = bitarray('10001100')
    assert c.adc_burst_length_data() == expected

def test_configuration_v1_channel_mask_data():
    c = Configuration_v1()
    c.channel_mask[4] = 1
    expected = bitarray('00010000')
    assert c.channel_mask_data(0) == expected
    c.channel_mask[10] = 1
    expected = bitarray('00000100')
    assert c.channel_mask_data(1) == expected
    c.channel_mask[20] = 1
    expected = bitarray('00010000')
    assert c.channel_mask_data(2) == expected
    c.channel_mask[30] = 1
    expected = bitarray('01000000')
    assert c.channel_mask_data(3) == expected

def test_configuration_v1_external_trigger_mask_data():
    c = Configuration_v1()
    c.external_trigger_mask[4] = 0
    expected = bitarray('11101111')
    assert c.external_trigger_mask_data(0) == expected
    c.external_trigger_mask[10] = 0
    expected = bitarray('11111011')
    assert c.external_trigger_mask_data(1) == expected
    c.external_trigger_mask[20] = 0
    expected = bitarray('11101111')
    assert c.external_trigger_mask_data(2) == expected
    c.external_trigger_mask[30] = 0
    expected = bitarray('10111111')
    assert c.external_trigger_mask_data(3) == expected

def test_configuration_v1_reset_cycles_data():
    c = Configuration_v1()
    c.reset_cycles = 0xabcdef
    expected = bah.fromuint(int('0xef', 16), 8)
    assert c.reset_cycles_data(0) == expected
    expected = bah.fromuint(int('0xcd', 16), 8)
    assert c.reset_cycles_data(1) == expected
    expected = bah.fromuint(int('0xab', 16), 8)
    assert c.reset_cycles_data(2) == expected

def test_configuration_v1_to_dict():
    c = Configuration_v1()
    attrs = [
            'pixel_trim_thresholds',
            'global_threshold',
            'csa_gain',
            'csa_bypass',
            'internal_bypass',
            'csa_bypass_select',
            'csa_monitor_select',
            'csa_testpulse_enable',
            'csa_testpulse_dac_amplitude',
            'test_mode',
            'cross_trigger_mode',
            'periodic_reset',
            'fifo_diagnostic',
            'sample_cycles',
            'test_burst_length',
            'adc_burst_length',
            'channel_mask',
            'external_trigger_mask',
            'reset_cycles']
    expected = {}
    for attr in attrs:
        expected[attr] = getattr(c, attr)
    result = c.to_dict()
    assert result == expected

def test_configuration_v1_from_dict():
    c = Configuration_v1()
    attrs = [
            'pixel_trim_thresholds',
            'global_threshold',
            'csa_gain',
            'csa_bypass',
            'internal_bypass',
            'csa_bypass_select',
            'csa_monitor_select',
            'csa_testpulse_enable',
            'csa_testpulse_dac_amplitude',
            'test_mode',
            'cross_trigger_mode',
            'periodic_reset',
            'fifo_diagnostic',
            'sample_cycles',
            'test_burst_length',
            'adc_burst_length',
            'channel_mask',
            'external_trigger_mask',
            'reset_cycles']
    expected = {}
    for attr in attrs:
        expected[attr] = getattr(c, attr)
    expected['global_threshold'] = 50
    c.from_dict(expected)
    result = c.to_dict()
    assert result == expected

def test_configuration_write(tmpdir):
    c = Configuration()
    f = str(tmpdir.join('test_config.json'))
    c.write(f)
    with open(f, 'r') as output:
        result = json.load(output)
    expected = c.to_dict()
    assert result['register_values'] == expected

def test_configuration_write_errors(tmpdir):
    c = Configuration()
    f = tmpdir.join('test_config.json')
    f.write("Test data.....")
    with pytest.raises(IOError):
        c.write(str(f))
        pytest.fail('Should fail: force fails')

def test_configuration_write_force(tmpdir):
    c = Configuration()
    f = tmpdir.join('test_config.json')
    f.write("Test data.....")
    c.write(str(f), force=True)
    with open(str(f), 'r') as output:
        result = json.load(output)
    expected = c.to_dict()
    assert result['register_values'] == expected

def test_configuration_v1_read_absolute(tmpdir):
    c = Configuration_v1()
    c.pixel_trim_thresholds[0] = 30
    c.reset_cycles = 0x100010
    f = str(tmpdir.join('test_config.json'))
    c.write(f)
    c2 = Configuration_v1()
    c2.load(f)
    expected = c.to_dict()
    result = c2.to_dict()
    assert result == expected

def test_configuration_v1_read_default():
    c = Configuration_v1()
    expected = c.to_dict()
    c.global_threshold = 100
    c.load('chip/default.json')
    result = c.to_dict()
    assert result == expected

def test_configuration_v1_read_local():
    c = Configuration_v1()
    c.global_threshold = 104
    expected = c.to_dict()
    abspath = os.path.join(os.getcwd(), 'test_config.json')
    c.write(abspath)
    c.global_threshold = 0x10
    c.load('test_config.json')
    result = c.to_dict()
    os.remove(abspath)
    assert result == expected

def test_configuration_v1_from_dict_reg_pixel_trim():
    c = Configuration_v1()
    register_dict = { 0: 5, 15: 20 }
    c.from_dict_registers(register_dict)
    result_1 = c.pixel_trim_thresholds[0]
    expected_1 = register_dict[0]
    assert result_1 == expected_1
    result_2 = c.pixel_trim_thresholds[15]
    expected_2 = register_dict[15]
    assert result_2 == expected_2

def test_configuration_v1_from_dict_reg_global_threshold():
    c = Configuration_v1()
    register_dict = { 32: 182 }
    c.from_dict_registers(register_dict)
    result = c.global_threshold
    expected = register_dict[32]
    assert result == expected

def test_configuration_v1_from_dict_reg_csa_gain():
    c = Configuration_v1()
    register_dict = { 33: 0 }
    c.from_dict_registers(register_dict)
    result = c.csa_gain
    expected = 0
    assert result == expected

def test_configuration_v1_from_dict_reg_csa_bypass():
    c = Configuration_v1()
    register_dict = { 33: 2 }
    c.from_dict_registers(register_dict)
    result = c.csa_bypass
    expected = 1
    assert result == expected

def test_configuration_v1_from_dict_reg_internal_bypass():
    c = Configuration_v1()
    register_dict = { 33: 8 }
    c.from_dict_registers(register_dict)
    result = c.internal_bypass
    expected = 1
    assert result == expected

def test_configuration_v1_from_dict_reg_csa_bypass_select():
    c = Configuration_v1()
    register_dict = { 34: 0x12, 35: 0x34, 36: 0x56, 37: 0x78 }
    c.from_dict_registers(register_dict)
    result = c.csa_bypass_select
    expected = [
            0, 1, 0, 0, 1, 0, 0, 0,
            0, 0, 1, 0, 1, 1, 0, 0,
            0, 1, 1, 0, 1, 0, 1, 0,
            0, 0, 0, 1, 1, 1, 1, 0
            ]
    assert result == expected

def test_configuration_v1_from_dict_reg_csa_monitor_select():
    c = Configuration_v1()
    register_dict = { 38: 0x12, 39: 0x34, 40: 0x56, 41: 0x78 }
    c.from_dict_registers(register_dict)
    result = c.csa_monitor_select
    expected = [
            0, 1, 0, 0, 1, 0, 0, 0,
            0, 0, 1, 0, 1, 1, 0, 0,
            0, 1, 1, 0, 1, 0, 1, 0,
            0, 0, 0, 1, 1, 1, 1, 0
            ]
    assert result == expected

def test_configuration_v1_from_dict_reg_csa_testpulse_enable():
    c = Configuration_v1()
    register_dict = { 42: 0x12, 43: 0x34, 44: 0x56, 45: 0x78 }
    c.from_dict_registers(register_dict)
    result = c.csa_testpulse_enable
    expected = [
            0, 1, 0, 0, 1, 0, 0, 0,
            0, 0, 1, 0, 1, 1, 0, 0,
            0, 1, 1, 0, 1, 0, 1, 0,
            0, 0, 0, 1, 1, 1, 1, 0
            ]
    assert result == expected

def test_configuration_v1_from_dict_reg_csa_testpulse_dac_amplitude():
    c = Configuration_v1()
    register_dict = { 46: 193 }
    c.from_dict_registers(register_dict)
    result = c.csa_testpulse_dac_amplitude
    expected = 193
    assert result == expected

def test_configuration_v1_from_dict_reg_test_mode():
    c = Configuration_v1()
    register_dict = { 47: 2 }
    c.from_dict_registers(register_dict)
    result = c.test_mode
    expected = 2
    assert result == expected

def test_configuration_v1_from_dict_reg_cross_trigger_mode():
    c = Configuration_v1()
    register_dict = { 47: 4 }
    c.from_dict_registers(register_dict)
    result = c.cross_trigger_mode
    expected = 1
    assert result == expected

def test_configuration_v1_from_dict_reg_periodic_reset():
    c = Configuration_v1()
    register_dict = { 47: 8 }
    c.from_dict_registers(register_dict)
    result = c.periodic_reset
    expected = 1
    assert result == expected

def test_configuration_v1_from_dict_reg_fifo_diagnostic():
    c = Configuration_v1()
    register_dict = { 47: 16 }
    c.from_dict_registers(register_dict)
    result = c.fifo_diagnostic
    expected = 1
    assert result == expected

def test_configuration_v1_from_dict_reg_sample_cycles():
    c = Configuration_v1()
    register_dict = { 48: 111 }
    c.from_dict_registers(register_dict)
    result = c.sample_cycles
    expected = 111
    assert result == expected

def test_configuration_v1_from_dict_reg_test_burst_length():
    c = Configuration_v1()
    register_dict = { 49: 5, 50: 2}
    c.from_dict_registers(register_dict)
    result = c.test_burst_length
    expected = 517  # = 256 * 2 + 1 * 5
    assert result == expected

def test_configuration__v1from_dict_reg_adc_burst_length():
    c = Configuration_v1()
    register_dict = { 51: 83 }
    c.from_dict_registers(register_dict)
    result = c.adc_burst_length
    expected = 83
    assert result == expected

def test_configuration_v1_from_dict_reg_channel_mask():
    c = Configuration_v1()
    register_dict = { 52: 0x12, 53: 0x34, 54: 0x56, 55: 0x78 }
    c.from_dict_registers(register_dict)
    result = c.channel_mask
    expected = [
            0, 1, 0, 0, 1, 0, 0, 0,
            0, 0, 1, 0, 1, 1, 0, 0,
            0, 1, 1, 0, 1, 0, 1, 0,
            0, 0, 0, 1, 1, 1, 1, 0
            ]
    assert result == expected

def test_configuration_v1_from_dict_reg_external_trigger_mask():
    c = Configuration_v1()
    register_dict = { 56: 0x12, 57: 0x34, 58: 0x56, 59: 0x78 }
    c.from_dict_registers(register_dict)
    result = c.external_trigger_mask
    expected = [
            0, 1, 0, 0, 1, 0, 0, 0,
            0, 0, 1, 0, 1, 1, 0, 0,
            0, 1, 1, 0, 1, 0, 1, 0,
            0, 0, 0, 1, 1, 1, 1, 0
            ]
    assert result == expected

def test_configuration_v1_from_dict_reg_reset_cycles():
    c = Configuration_v1()
    register_dict = { 60: 0x12, 61: 0x34, 62: 0x56 }
    c.from_dict_registers(register_dict)
    result = c.reset_cycles
    expected = 0x563412
    assert result == expected

def test_controller_get_chip(chip):
    controller = Controller()
    chip_key = chip.chip_key
    controller.chips[chip_key] = chip
    assert controller[chip_key] == chip
    assert controller[tuple(chip_key)] == chip
    assert controller[chip_key.keystring] == chip

def test_controller_get_chip_error(chip):
    controller = Controller()
    controller.chips[chip.chip_key] = chip
    test_key_dict = chip.chip_key.to_dict()
    test_key_dict['chip_id'] += 1
    test_key = Key.from_dict(test_key_dict)
    with pytest.raises(ValueError):
        controller[test_key]
    test_key_dict = chip.chip_key.to_dict()
    test_key_dict['io_channel'] += 1
    test_key = Key.from_dict(test_key_dict)
    with pytest.raises(ValueError):
        controller[test_key]
    test_key_dict = chip.chip_key.to_dict()
    test_key_dict['io_group'] += 1
    test_key = Key.from_dict(test_key_dict)
    with pytest.raises(ValueError):
        controller[test_key]

def test_controller_read():
    controller = Controller()
    controller.io = FakeIO()
    controller.io.queue.append(([Packet()], b'\x00\x00'))
    controller.start_listening()
    result = controller.read()
    controller.stop_listening()
    expected =([Packet()], b'\x00\x00')
    assert result == expected

def test_controller_send(capfd):
    controller = Controller()
    controller.io = FakeIO()
    to_send = [Packet(b'0'*Packet.num_bytes), Packet(b'a'*Packet.num_bytes)]
    controller.send(to_send)
    result, err = capfd.readouterr()
    expected = list_of_packets_str(to_send)
    assert result == expected

def test_controller_load():
    controller = Controller()
    controller.io = FakeIO()
    controller.load('controller/pcb-1_chip_info.json')

def test_controller_read_configuration(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    controller.chips[chip.chip_key] = chip
    conf_data = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    sent_expected = list_of_packets_str(conf_data)
    controller.io.queue.append((conf_data,b'hi'))
    received_expected = PacketCollection(conf_data, b'hi', read_id=0,
            message='configuration read')
    controller.read_configuration(chip.chip_key, timeout=0.01)
    received_result = controller.reads[-1]
    sent_result, err = capfd.readouterr()
    assert sent_result == sent_expected
    assert received_result == received_expected

def test_controller_read_configuration_reg(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    controller.chips[chip.chip_key] = chip
    conf_data = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)[0:1]
    sent_expected = list_of_packets_str(conf_data)
    controller.io.queue.append((conf_data,b'hi'))
    received_expected = PacketCollection(conf_data, b'hi', read_id=0,
            message='configuration read')
    controller.read_configuration(chip.chip_key, 0, timeout=0.01)
    received_result = controller.reads[-1]
    sent_result, err = capfd.readouterr()
    assert sent_result == sent_expected
    assert received_result == received_expected

def test_controller_write_configuration(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    controller.chips[chip.chip_key] = chip
    controller.write_configuration(chip.chip_key)
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    expected = list_of_packets_str(conf_data)
    result, err = capfd.readouterr()
    assert result == expected

def test_controller_write_configuration_one_reg(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    controller.chips[chip.chip_key] = chip
    controller.write_configuration(chip.chip_key, 0)
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)[0:1]
    expected = list_of_packets_str(conf_data)
    result, err = capfd.readouterr()
    assert result == expected

def test_controller_write_configuration_write_read(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    controller.chips[chip.chip_key] = chip
    to_read = ([Packet(b'1'*Packet.num_bytes)], b'hi')
    controller.io.queue.append(to_read)
    expected_read = PacketCollection(*to_read, read_id=0,
            message='configuration write')
    controller.write_configuration(chip.chip_key, registers=5, write_read=0.1)
    result_read = controller.reads[0]
    assert result_read == expected_read
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)[5:6]
    expected_sent = list_of_packets_str(conf_data)
    result_sent, err = capfd.readouterr()
    assert result_sent == expected_sent

def test_controller_multi_write_configuration(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    key = chip.chip_key
    key2_dict = chip.chip_key.to_dict()
    key2_dict['chip_id'] += 1
    key2 = Key.from_dict(key2_dict)
    chip2 = Chip(key2)
    controller.chips = {key:chip, key2:chip2}
    controller.multi_write_configuration((key, key2))
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    conf_data2 = chip2.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    final_string_1 = list_of_packets_str(conf_data)
    final_string_2 = list_of_packets_str(conf_data2)
    expected = final_string_1 + final_string_2
    result, err = capfd.readouterr()
    assert result == expected

def test_controller_multi_write_configuration_write_read(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    to_read = ([Packet(b'1'*Packet.num_bytes)], b'hi')
    controller.io.queue.append(to_read)
    expected_read = PacketCollection(*to_read, read_id=0,
            message='configuration write')
    key = chip.chip_key
    key2_dict = chip.chip_key.to_dict()
    key2_dict['chip_id'] += 1
    key2 = Key.from_dict(key2_dict)
    chip2 = Chip(key2)
    controller.chips = {key:chip, key2:chip2}
    controller.multi_write_configuration((key, key2), write_read=0.01)
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    conf_data2 = chip2.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    final_string_1 = list_of_packets_str(conf_data)
    final_string_2 = list_of_packets_str(conf_data2)
    expected = final_string_1 + final_string_2
    result, err = capfd.readouterr()
    assert result == expected

def test_controller_multi_write_configuration_specify_registers(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    key = chip.chip_key
    key2_dict = chip.chip_key.to_dict()
    key2_dict['chip_id'] += 1
    key2 = Key.from_dict(key2_dict)
    chip2 = Chip(key2)
    controller.chips = {key:chip, key2:chip2}
    controller.multi_write_configuration([(key, 0), key2])
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)[:1]
    conf_data2 = chip2.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    final_string_1 = list_of_packets_str(conf_data)
    final_string_2 = list_of_packets_str(conf_data2)
    expected = final_string_1 + final_string_2
    result, err = capfd.readouterr()
    assert result == expected


def test_controller_multi_read_configuration(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    controller.use_all_chips = True
    key0_dict = chip.chip_key.to_dict()
    key0_dict['io_channel'] = 1
    key0_dict['chip_key'] = 1
    key0 = Key.from_dict(key0_dict)
    key1_dict = chip.chip_key.to_dict()
    key1_dict['chip_id'] += 1
    key1_dict['io_channel'] = 1
    key1_dict['chip_key'] = 1
    key1 = Key.from_dict(key1_dict)
    chip1 = controller.add_chip(key0)
    chip2 = controller.add_chip(key1)
    conf_data = chip1.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    conf_data2 = chip2.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    final_string_1 = list_of_packets_str(conf_data)
    final_string_2 = list_of_packets_str(conf_data2)
    expected_sent = final_string_1 + final_string_2
    controller.io.queue.append((conf_data+conf_data2, b'hi'))
    expected_read = PacketCollection(conf_data+conf_data2, b'hi',
            read_id=0, message='multi configuration read')
    controller.multi_read_configuration((key0, key1), timeout=0.01)
    result_sent, err = capfd.readouterr()
    result_read = controller.reads[-1]
    assert result_sent == expected_sent
    assert result_read == expected_read

def test_controller_multi_read_configuration_specify_registers(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    key0 = Key(chip.chip_key)
    key1_dict = chip.chip_key.to_dict()
    key1_dict['chip_id'] += 1
    key1 = Key.from_dict(key1_dict)
    controller.chips[key0] = Chip(chip_key=key0)
    controller.chips[key1] = Chip(chip_key=key1)
    conf_data = controller.chips[key0].get_configuration_packets(Packet.CONFIG_READ_PACKET)[:1]
    conf_data2 = controller.chips[key1].get_configuration_packets(Packet.CONFIG_READ_PACKET)
    final_string_1 = list_of_packets_str(conf_data)
    final_string_2 = list_of_packets_str(conf_data2)
    expected_sent = final_string_1 + final_string_2
    controller.io.queue.append((conf_data+conf_data2, b'hi'))
    expected_read = PacketCollection(conf_data+conf_data2, b'hi',
            read_id=0, message='multi configuration read')
    controller.multi_read_configuration([(key0, 0), key1], timeout=0.01)
    result_sent, err = capfd.readouterr()
    result_read = controller.reads[-1]
    assert result_sent == expected_sent
    assert result_read == expected_read

def test_controller_verify_configuration_ok(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    controller.chips[chip.chip_key] = chip
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    for packet in conf_data: packet.packet_type = Packet.CONFIG_READ_PACKET
    controller.io.queue.append((conf_data,b'hi'))
    ok, diff = controller.verify_configuration(chip_keys=chip.chip_key)
    assert diff == {}
    assert ok

def test_controller_verify_configuration_missing_packet(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    controller.chips[chip.chip_key] = chip
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    for packet in conf_data: packet.packet_type = Packet.CONFIG_READ_PACKET
    del conf_data[5]
    controller.io.queue.append((conf_data,b'hi'))
    ok, diff = controller.verify_configuration(chip_keys=chip.chip_key)
    assert ok == False
    assert diff == {chip.chip_key: {5: (16, None)}}

def test_controller_verify_configuration_bad_value(capfd, chip):
    controller = Controller()
    controller.io = FakeIO()
    controller.chips[chip.chip_key] = chip
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    for packet in conf_data: packet.packet_type = Packet.CONFIG_READ_PACKET
    conf_data[5].register_data = 17
    controller.io.queue.append((conf_data,b'hi'))
    ok, diff = controller.verify_configuration(chip_keys=chip.chip_key)
    assert ok == False
    assert diff == {chip.chip_key: {5: (16, 17)}}

def test_packetcollection_getitem_int():
    expected = Packet()
    collection = PacketCollection([expected])
    result = collection[0]
    assert result == expected

def test_packetcollection_getitem_int_bits(timestamp_packet):
    packet = Packet()
    collection = PacketCollection([packet])
    result = collection[0, 'bits']
    expected = ' '.join(packet.bits.to01()[i:i+8] for i in range(0, Packet.size, 8))
    assert result == expected
    packet2 = timestamp_packet
    collection2 = PacketCollection([packet2])
    result2 = collection2[0, 'bits']
    expected2 = ' '.join(packet2.bits.to01()[i:i+8] for i in range(0,
        packet2.size, 8))
    assert result2 == expected2

def test_packetcollection_getitem_slice(chip):
    packets = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    collection = PacketCollection(packets, message='hello')
    result = collection[:10]
    expected = PacketCollection(packets[:10], message='hello'
        ' | subset slice(None, 10, None)')
    assert result == expected

def test_packetcollection_getitem_slice_bits(chip):
    packets = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    collection = PacketCollection(packets, message='hello')
    result = collection[:10, 'bits']
    expected = [' '.join(p.bits.to01()[i:i+8] for i in range(0,
        Packet.size, 8)) for p in packets[:10]]
    assert result == expected

def test_packetcollection_origin(chip):
    packets = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    collection = PacketCollection(packets, message='hello')
    first_gen = collection.by_chipid()[chip.chip_id]
    second_gen = first_gen.by_chipid()[chip.chip_id]
    assert first_gen.parent is collection
    assert first_gen.origin() is collection
    assert second_gen.parent is first_gen
    assert second_gen.origin() is collection

def test_packetcollection_v2_extract():
    p1 = Packet_v2()
    p1.chip_id = 10
    p1.packet_type = Packet_v2.DATA_PACKET
    p1.dataword = 36
    p2 = Packet_v2()
    p2.chip_id = 9
    p2.packet_type = Packet_v2.DATA_PACKET
    p2.dataword = 38
    p3 = Packet_v2()
    p3.chip_id = 8
    p3.packet_type = Packet_v2.TEST_PACKET
    pc = PacketCollection([p1,p2,p3])
    expected = [10, 9, 8]
    assert pc.extract('chip_id') == expected
    expected = [36, 38]
    assert pc.extract('dataword', packet_type=Packet_v2.DATA_PACKET) == expected
    expected = [36]
    assert pc.extract('dataword', chip_id=10, packet_type=Packet_v2.DATA_PACKET) == expected
    expected = [[10,36],[9,38]]
    assert pc.extract('chip_id','dataword', packet_type=Packet_v2.DATA_PACKET) == expected

def test_packetcollection_to_dict():
    packet = Packet()
    packet.chip_id = 246
    packet.packet_type = Packet.TEST_PACKET
    collection = PacketCollection([packet], bytestream=packet.bytes(),
            message='hello')
    result = collection.to_dict()
    expected = {
            'id': id(collection),
            'parent': 'None',
            'message': 'hello',
            'read_id': 'None',
            'bytestream': packet.bytes().decode('raw_unicode_escape'),
            'packets': [packet.export()]
            }
    assert result == expected

def test_packetcollection_from_dict():
    packet = Packet()
    packet.packet_type = Packet.TEST_PACKET
    collection = PacketCollection([packet], bytestream=packet.bytes(),
            message='hello')
    d = collection.to_dict()
    result = PacketCollection([])
    result.from_dict(d)
    expected = collection
    assert result == expected

def test_Smart_List_init_wrong_type():
    with pytest.raises(ValueError):
        sl = _Smart_List(5, 0, 40)
        pytest.fail('Should fail: wrong type')

def test_Smart_List_init_out_of_bounds():
    with pytest.raises(ValueError):
        sl = _Smart_List([-1], 0, 40)
        pytest.fail('Should fail: out of bounds')

def test_Smart_List_assignment():
    result = _Smart_List([1,2,3],0,40)
    expected = [1,2,3]
    assert result == expected
    result[0] = 20
    expected = [20,2,3]
    assert result == expected

def test_Smart_List_error():
    sl = _Smart_List([1,2,3],0,40)
    with pytest.raises(ValueError):
        sl[0] = 41
        pytest.fail('Should fail: out of bounds')

def test_Smart_List_slice_error():
    sl = _Smart_List(list(range(10)), 0, 40)
    with pytest.raises(ValueError):
        sl[5:7] = [40, 41, 40]
        pytest.fail('Should fail: out of bounds')

def test_Smart_List_config_error():
    c = Configuration()
    register_dict = { 0: 5, 15: 89 }
    with pytest.raises(ValueError):
        c.from_dict_registers(register_dict)
        pytest.fail('Should fail: out of bounds')

def test_ts_packet_to_dict(timestamp_packet):
    packet_dict = {
            'bits': timestamp_packet.bits.to01(),
            'type_str': 'timestamp',
            'type': timestamp_packet.packet_type,
            'timestamp': timestamp_packet.timestamp,
            }
    assert timestamp_packet.export() == packet_dict

def test_ts_packet_from_dict(timestamp_packet):
    p1 = TimestampPacket()
    packet_dict = {
            'bits': timestamp_packet.bits.to01(),
            'type_str': 'timestamp',
            'type': timestamp_packet.packet_type,
            'timestamp': timestamp_packet.timestamp,
            }
    p1.from_dict(packet_dict)
    assert timestamp_packet == p1

def test_ts_packet_from_dict_export_inv(timestamp_packet):
    p1 = TimestampPacket()
    p1.from_dict(timestamp_packet.export())
    assert timestamp_packet == p1

def test_message_packet_to_dict(message_packet):
    packet_dict = {
            'bits': message_packet.bits.to01(),
            'type_str': 'message',
            'message': message_packet.message,
            'type': message_packet.packet_type,
            'timestamp': message_packet.timestamp,
            }
    assert message_packet.export() == packet_dict

def test_message_packet_from_dict(message_packet):
    p1 = MessagePacket(None,None)
    packet_dict = {
            'bits': message_packet.bits.to01(),
            'type_str': 'message',
            'message': message_packet.message,
            'type': message_packet.packet_type,
            'timestamp': message_packet.timestamp,
            }
    p1.from_dict(packet_dict)
    assert message_packet == p1

def test_message_packet_from_dict_export_inv(message_packet):
    p1 = MessagePacket(None,None)
    p1.from_dict(message_packet.export())
    assert message_packet == p1

def test_key():
    with pytest.raises(ValueError):
        k = Key('0.0.0')
        pytest.fail('key is not proper format')
    with pytest.raises(ValueError):
        k = Key('256-0-0')
        pytest.fail('key value is not 1-byte')
    with pytest.raises(ValueError):
        k = Key(256,0,0)
        pytest.fail('key value is not 1-byte')
    with pytest.raises(TypeError):
        k = Key(250,0,0,1)
        pytest.fail('too many args')

    k = Key('1-2-3')
    with pytest.raises(AttributeError):
        k.io_channel = 1
        pytest.fail('key is pseudo immutable')
    with pytest.raises(AttributeError):
        k.io_group = 1
        pytest.fail('key is pseudo immutable')
    with pytest.raises(AttributeError):
        k.chip_id = 1
        pytest.fail('key is pseudo immutable')

    assert k == '1-2-3'
    assert Key(k) == k
    assert k.is_valid_keystring('0-0-256') == False
    assert k.is_valid_keystring('0-256-0') == False
    assert k.is_valid_keystring('256-0-0') == False
    assert k.is_valid_keystring('0 0 0') == False
    assert k.to_dict() == { 'io_group':1, 'io_channel':2, 'chip_id':3}
    test_dict = {'io_group':3, 'io_channel':2, 'chip_id':1}
    assert k.from_dict(test_dict) == Key('3-2-1')

    # test that you can hash a dict with the keys
    d = {}
    d[k] = 'test'
    assert d[k] == 'test'
