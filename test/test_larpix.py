'''
Use the pytest framework to write tests for the larpix module.

'''
import pytest
from larpix.larpix import Chip, Packet, Configuration, Controller
from bitstring import BitArray

def test_chip_get_configuration_packets():
    chip = Chip(3, 1)
    packet_type = Packet.CONFIG_WRITE_PACKET
    packets = chip.get_configuration_packets(packet_type)
    # test a sampling of the configuration packets
    packet = packets[5]
    assert packet.packet_type == packet_type
    assert packet.chipid == chip.chip_id
    assert packet.register_address == 5
    assert packet.register_data == 16

    packet = packets[40]
    assert packet.packet_type == packet_type
    assert packet.chipid == chip.chip_id
    assert packet.register_address == 40
    assert packet.register_data == 255

def test_packet_bits_bytes():
    assert Packet.num_bytes == Packet.size // 8 + 1

def test_packet_init_default():
    p = Packet()
    expected = BitArray(Packet.size)
    assert p.bits == expected

def test_packet_init_bytestream():
    bytestream = b'\x3f' + b'\x00' * (Packet.num_bytes-2) + b'\x3e'
    p = Packet(bytestream)
    expected = BitArray(Packet.size)
    expected[-6:] = [1]*6
    expected[:5] = [1]*5
    assert p.bits == expected

def test_packet_bytes_zeros():
    p = Packet()
    b = p.bytes()
    expected = b'\x00' * ((Packet.size + len(p._bit_padding))//8)
    assert b == expected

def test_packet_bytes_custom():
    p = Packet()
    p.bits[-6:] = [1]*6  # First byte is 0b00111111
    p.bits[:5] = [1]*5  # Last byte is 0b00111110 (2 MSBs are padding)
    b = p.bytes()
    expected = b'\x3f' + b'\x00' * (Packet.size//8-1) + b'\x3e'
    assert b == expected

def test_packet_bytes_properties():
    p = Packet()
    p.packet_type = Packet.DATA_PACKET
    p.chipid = 100
    expected = b'\x91\x01' + b'\x00' * (Packet.size//8-1)
    b = p.bytes()
    assert b == expected

def test_packet_set_packet_type():
    p = Packet()
    p.packet_type = Packet.DATA_PACKET
    packet_bits = p.bits[Packet.packet_type_bits]
    expected = Packet.DATA_PACKET
    assert packet_bits == expected

def test_packet_get_packet_type():
    p = Packet()
    p.packet_type = Packet.CONFIG_WRITE_PACKET
    packet_type = p.packet_type
    expected = Packet.CONFIG_WRITE_PACKET
    assert packet_type == expected

def test_packet_set_chipid():
    p = Packet()
    p.chipid = 121
    expected = BitArray('uint:8=121')
    assert p.bits[Packet.chipid_bits] == expected

def test_packet_get_chipid():
    p = Packet()
    p.chipid = 18
    expected = 18
    assert p.chipid == expected

def test_packet_set_parity_bit_value():
    p = Packet()
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

def test_packet_compute_parity():
    p = Packet()
    p.chipid = 121
    parity = p.compute_parity()
    expected = 0
    assert parity == expected

def test_packet_assign_parity():
    p = Packet()
    p.chipid = 121
    p.assign_parity()
    expected = 0
    assert p.parity_bit_value == expected
    p.chipid = 0
    p.assign_parity()
    expected = 1
    assert p.parity_bit_value == expected

def test_packet_set_register_address():
    p = Packet()
    p.register_address = 121
    expected = BitArray('uint:8=121')
    assert p.bits[Packet.register_address_bits] == expected

def test_packet_get_register_address():
    p = Packet()
    p.register_address = 18
    expected = 18
    assert p.register_address == expected

def test_packet_set_register_data():
    p = Packet()
    p.register_data = 1
    expected = BitArray('uint:8=1')
    assert p.bits[Packet.register_data_bits] == expected

def test_packet_get_register_data():
    p = Packet()
    p.register_data = 18
    expected = 18
    assert p.register_data == expected

def test_configuration_disable_channels():
    c = Configuration()
    expected = [0, 1] * 16
    c.disable_channels(range(1, 32, 2))
    assert c.channel_mask == expected

def test_configuration_disable_channels_default():
    c = Configuration()
    expected = [1] * 32
    c.disable_channels()
    assert c.channel_mask == expected

def test_configuration_enable_channels():
    c = Configuration()
    expected = [0, 1] * 16
    c.disable_channels()
    c.enable_channels(range(0, 32, 2))
    assert c.channel_mask == expected

def test_configuration_enable_channels_default():
    c = Configuration()
    expected = [0] * 32
    c.disable_channels()
    c.enable_channels()
    assert c.channel_mask == expected

@pytest.mark.xfail
def test_configuration_enable_normal_operation():
    assert 1 == 0

def test_configuration_enable_external_trigger():
    c = Configuration()
    expected = [0, 1] * 16
    c.enable_external_trigger(range(0, 32, 2))
    assert c.external_trigger_mask == expected

def test_configuration_enable_external_trigger_default():
    c = Configuration()
    expected = [0] * 32
    c.enable_external_trigger()
    assert c.external_trigger_mask == expected

def test_configuration_disable_external_trigger():
    c = Configuration()
    expected = [0, 1] * 16
    c.enable_external_trigger()
    c.disable_external_trigger(range(1, 32, 2))
    assert c.external_trigger_mask == expected

def test_configuration_enable_testpulse():
    c = Configuration()
    expected = [0, 1] * 16
    c.enable_testpulse(range(1, 32, 2))
    assert c.csa_testpulse_enable == expected

def test_configuration_enable_testpulse_default():
    c = Configuration()
    expected = [1] * 32
    c.enable_testpulse()
    assert c.csa_testpulse_enable == expected

def test_configuration_disable_testpulse():
    c = Configuration()
    expected = [0, 1] * 16
    c.enable_testpulse()
    c.disable_testpulse(range(0, 32, 2))
    assert c.csa_testpulse_enable == expected

def test_configuration_disable_testpulse_default():
    c = Configuration()
    expected = [0] * 32
    c.enable_testpulse()
    c.disable_testpulse()
    assert c.csa_testpulse_enable == expected

def test_configuration_enable_analog_monitor():
    c = Configuration()
    expected = [1, 1, 0] + [1] * 29
    c.enable_analog_monitor(2)
    assert c.csa_monitor_select == expected

def test_configuration_disable_analog_monitor():
    c = Configuration()
    expected = [1] * 32
    c.enable_analog_monitor(5)
    c.disable_analog_monitor()
    assert c.csa_monitor_select == expected

def test_configuration_trim_threshold_data():
    c = Configuration()
    expected = BitArray('0x10')
    assert c.trim_threshold_data(0) == expected

def test_configuration_global_threshold_data():
    c = Configuration()
    expected = BitArray('0x10')
    assert c.global_threshold_data() == expected

def test_configuration_csa_gain_and_bypasses_data():
    c = Configuration()
    expected = BitArray('0b00001001')
    assert c.csa_gain_and_bypasses_data() == expected

def test_configuration_csa_bypass_select_data():
    c = Configuration()
    c.csa_bypass_select[4] = 1
    expected = BitArray('0b00010000')
    assert c.csa_bypass_select_data(0) == expected
    c.csa_bypass_select[10] = 1
    expected = BitArray('0b00000100')
    assert c.csa_bypass_select_data(1) == expected
    c.csa_bypass_select[20] = 1
    expected = BitArray('0b00010000')
    assert c.csa_bypass_select_data(2) == expected
    c.csa_bypass_select[30] = 1
    expected = BitArray('0b01000000')
    assert c.csa_bypass_select_data(3) == expected

def test_configuration_csa_monitor_select_data():
    c = Configuration()
    c.csa_monitor_select[4] = 0
    expected = BitArray('0b11101111')
    assert c.csa_monitor_select_data(0) == expected
    c.csa_monitor_select[10] = 0
    expected = BitArray('0b11111011')
    assert c.csa_monitor_select_data(1) == expected
    c.csa_monitor_select[20] = 0
    expected = BitArray('0b11101111')
    assert c.csa_monitor_select_data(2) == expected
    c.csa_monitor_select[30] = 0
    expected = BitArray('0b10111111')
    assert c.csa_monitor_select_data(3) == expected

def test_configuration_csa_testpulse_enable_data():
    c = Configuration()
    c.csa_testpulse_enable[4] = 1
    expected = BitArray('0b00010000')
    assert c.csa_testpulse_enable_data(0) == expected
    c.csa_testpulse_enable[10] = 1
    expected = BitArray('0b00000100')
    assert c.csa_testpulse_enable_data(1) == expected
    c.csa_testpulse_enable[20] = 1
    expected = BitArray('0b00010000')
    assert c.csa_testpulse_enable_data(2) == expected
    c.csa_testpulse_enable[30] = 1
    expected = BitArray('0b01000000')
    assert c.csa_testpulse_enable_data(3) == expected

def test_configuration_csa_testpulse_dac_amplitude_data():
    c = Configuration()
    c.csa_testpulse_dac_amplitude = 200;
    expected = BitArray('0b11001000')
    assert c.csa_testpulse_dac_amplitude_data() == expected

def test_configuration_test_mode_xtrig_reset_diag_data():
    c = Configuration()
    c.test_mode = 2
    c.fifo_diagnostic = 1
    expected = BitArray('0b00010010')
    assert c.test_mode_xtrig_reset_diag_data() == expected

def test_configuration_sample_cycles_data():
    c = Configuration()
    c.sample_cycles = 221
    expected = BitArray('0b11011101')
    assert c.sample_cycles_data() == expected

def test_configuration_test_burst_length_data():
    c = Configuration()
    expected = BitArray('0xFF')
    assert c.test_burst_length_data(0) == expected
    expected = BitArray('0x00')
    assert c.test_burst_length_data(1) == expected

def test_configuration_adc_burst_length_data():
    c = Configuration()
    c.adc_burst_length = 140
    expected = BitArray('0b10001100')
    assert c.adc_burst_length_data() == expected

def test_configuration_channel_mask_data():
    c = Configuration()
    c.channel_mask[4] = 1
    expected = BitArray('0b00010000')
    assert c.channel_mask_data(0) == expected
    c.channel_mask[10] = 1
    expected = BitArray('0b00000100')
    assert c.channel_mask_data(1) == expected
    c.channel_mask[20] = 1
    expected = BitArray('0b00010000')
    assert c.channel_mask_data(2) == expected
    c.channel_mask[30] = 1
    expected = BitArray('0b01000000')
    assert c.channel_mask_data(3) == expected

def test_configuration_external_trigger_mask_data():
    c = Configuration()
    c.external_trigger_mask[4] = 0
    expected = BitArray('0b11101111')
    assert c.external_trigger_mask_data(0) == expected
    c.external_trigger_mask[10] = 0
    expected = BitArray('0b11111011')
    assert c.external_trigger_mask_data(1) == expected
    c.external_trigger_mask[20] = 0
    expected = BitArray('0b11101111')
    assert c.external_trigger_mask_data(2) == expected
    c.external_trigger_mask[30] = 0
    expected = BitArray('0b10111111')
    assert c.external_trigger_mask_data(3) == expected

def test_configuration_reset_cycles_data():
    c = Configuration()
    c.reset_cycles = 0xabcdef
    expected = BitArray('0xef')
    assert c.reset_cycles_data(0) == expected
    expected = BitArray('0xcd')
    assert c.reset_cycles_data(1) == expected
    expected = BitArray('0xab')
    assert c.reset_cycles_data(2) == expected

def test_controller_format_UART():
    controller = Controller(None)
    chip = Chip(2, 4)
    packet = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)[10]
    result = controller.format_UART(chip, packet)
    expected = b'\x73' + packet.bytes() + b'\x04\x71'
    assert result == expected

def test_controller_format_bytestream():
    controller = Controller(None)
    chip = Chip(2, 4)
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [controller.format_UART(chip, p) for p in packets]
    result = controller.format_bytestream(fpackets[:1])
    assert result == fpackets[:1]
    result = controller.format_bytestream(fpackets[:2])
    assert result == [b''.join(fpackets[:2])]
    result = controller.format_bytestream(fpackets[:1]*2000)
    expected = []
    expected.append(b''.join(fpackets[:1]*819))
    expected.append(b''.join(fpackets[:1]*819))
    expected.append(b''.join(fpackets[:1]*362))
    assert result == expected

def test_controller_write_configuration():
    controller = Controller(None)
    controller._test_mode = True
    chip = Chip(2, 4)
    result = controller.write_configuration(chip)
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    expected = controller.format_bytestream([controller.format_UART(chip, conf_data_i) for
            conf_data_i in conf_data])
    assert result == expected

def test_controller_write_configuration_one_reg():
    controller = Controller(None)
    controller._test_mode = True
    chip = Chip(2, 4)
    result = controller.write_configuration(chip, 0)
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)[0]
    expected = [controller.format_UART(chip, conf_data)]
    assert result == expected

def test_controller_parse_input():
    controller = Controller(None)
    chip = Chip(2, 4)
    controller.chips.append(chip)
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [controller.format_UART(chip, p) for p in packets]
    bytestream = b''.join(controller.format_bytestream(fpackets))
    remainder_bytes = controller.parse_input(bytestream)
    expected_remainder_bytes = b''
    assert remainder_bytes == expected_remainder_bytes
    result = chip.reads
    expected = packets
    assert result == expected

def test_controller_parse_input_dropped_data_byte():
    # Test whether the parser can recover from dropped bytes
    controller = Controller(None)
    chip = Chip(2, 4)
    controller.chips.append(chip)
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [controller.format_UART(chip, p) for p in packets]
    bytestream = b''.join(controller.format_bytestream(fpackets))
    # Drop a byte in the first packet
    bytestream_faulty = bytestream[1:]
    remainder_bytes = controller.parse_input(bytestream_faulty)
    expected_remainder_bytes = b''
    assert remainder_bytes == expected_remainder_bytes
    result = chip.reads
    expected = packets[1:]
    assert result == expected

def test_controller_parse_input_dropped_start_byte():
    controller = Controller(None)
    chip = Chip(2, 4)
    controller.chips.append(chip)
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [controller.format_UART(chip, p) for p in packets]
    bytestream = b''.join(controller.format_bytestream(fpackets))
    # Drop the first start byte
    bytestream_faulty = bytestream[1:]
    remainder_bytes = controller.parse_input(bytestream_faulty)
    expected_remainder_bytes = b''
    assert remainder_bytes == expected_remainder_bytes
    result = chip.reads
    expected = packets[1:]
    assert result == expected

def test_controller_parse_input_dropped_stop_byte():
    controller = Controller(None)
    chip = Chip(2, 4)
    controller.chips.append(chip)
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [controller.format_UART(chip, p) for p in packets]
    bytestream = b''.join(controller.format_bytestream(fpackets))
    # Drop the first stop byte
    bytestream_faulty = bytestream[:9] + bytestream[10:]
    remainder_bytes = controller.parse_input(bytestream_faulty)
    expected_remainder_bytes = b''
    assert remainder_bytes == expected_remainder_bytes
    result = chip.reads
    expected = packets[1:]
    assert result == expected

def test_controller_parse_input_dropped_stopstart_bytes():
    controller = Controller(None)
    chip = Chip(2, 4)
    controller.chips.append(chip)
    packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    fpackets = [controller.format_UART(chip, p) for p in packets]
    bytestream = b''.join(controller.format_bytestream(fpackets))
    # Drop the first stop byte
    bytestream_faulty = bytestream[:9] + bytestream[11:]
    remainder_bytes = controller.parse_input(bytestream_faulty)
    expected_remainder_bytes = b''
    assert remainder_bytes == expected_remainder_bytes
    result = chip.reads
    expected = packets[2:]
    assert result == expected
