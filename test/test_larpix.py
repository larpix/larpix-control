'''
Use the pytest framework to write tests for the larpix module.

'''
from __future__ import print_function
import pytest
from larpix.larpix import Chip, Packet, Configuration, Controller
from bitstring import BitArray
import json

class MockSerialPort(object):
    '''
    This class implements the interface of the pyserial Serial class so
    that we can test the serial_read, serial_write, etc. methods of the
    Controller class.

    '''
    data_to_mock_read = None
    def __init__(self, port=None, baudrate=9600, timeout=None):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.read_index = 0

    def write(self, data):
        print(bytes2str(data), sep='', end='')

    def read(self, nbytes):
        read_index = self.read_index
        data = MockSerialPort.data_to_mock_read[read_index:read_index+nbytes]
        self.read_index = read_index+nbytes
        return data

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

def bytes2str(bytestream):
    return ' '.join('{:02x}'.format(byte) for byte in
            bytearray(bytestream))

def test_MockSerialPort_write(capfd):
    serial = MockSerialPort()
    to_write = b'Hello'
    serial.write(b'Hello')
    out, err = capfd.readouterr()
    expected = bytes2str(to_write)
    assert out == expected

def test_MockSerialPort_read():
    serial = MockSerialPort()
    expected = bytes(bytearray(10))
    MockSerialPort.data_to_mock_read = expected
    data = serial.read(10)
    assert data == expected

def test_MockSerialPort_read_multi():
    serial = MockSerialPort()
    expected = bytes(bytearray(range(10)))
    MockSerialPort.data_to_mock_read = expected
    data = serial.read(5)
    data += serial.read(5)
    data += serial.read(5)
    assert data == expected

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
    expected = BitArray([0] * Packet.size)
    assert p.bits == expected

def test_packet_init_bytestream():
    bytestream = b'\x3f' + b'\x00' * (Packet.num_bytes-2) + b'\x3e'
    p = Packet(bytestream)
    expected = BitArray([0] * Packet.size)
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
    p.bits = BitArray([0]*54)
    parity = p.compute_parity()
    expected = 1
    assert parity == expected
    p.bits = BitArray([1]*54)
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

def test_packet_has_valid_parity():
    p = Packet()
    result = p.has_valid_parity()
    expected = False
    assert result == expected
    p.assign_parity()
    result = p.has_valid_parity()
    expected = True
    assert result == expected
    p.bits = BitArray([1]*54)
    result = p.has_valid_parity()
    expected = False
    assert result == expected
    p.assign_parity()
    result = p.has_valid_parity()
    expected = True
    assert result == expected

def test_packet_set_channel_id():
    p = Packet()
    p.channel_id = 100
    expected = BitArray('uint:7=100')
    assert p.bits[Packet.channel_id_bits] == expected

def test_packet_get_channel_id():
    p = Packet()
    expected = 101
    p.channel_id = expected
    assert p.channel_id == expected

def test_packet_set_timestamp():
    p = Packet()
    p.timestamp = 0x1327ab
    expected = BitArray('0x1327ab')
    assert p.bits[Packet.timestamp_bits] == expected

def test_packet_get_timestamp():
    p = Packet()
    expected = 0xa82b6e
    p.timestamp = expected
    assert p.timestamp == expected

def test_packet_set_dataword():
    p = Packet()
    p.dataword = 75
    expected = BitArray('uint:10=75')
    assert p.bits[Packet.dataword_bits] == expected

def test_packet_get_dataword():
    p = Packet()
    expected = 75
    p.dataword = expected
    assert p.dataword == expected

def test_packet_set_fifo_half_flag():
    p = Packet()
    p.fifo_half_flag = 1
    expected = True
    assert p.bits[Packet.fifo_half_bit] == expected

def test_packet_get_fifo_half_flag():
    p = Packet()
    expected = 1
    p.fifo_half_flag = expected
    assert p.fifo_half_flag == expected

def test_packet_set_fifo_full_flag():
    p = Packet()
    p.fifo_full_flag = 1
    expected = True
    assert p.bits[Packet.fifo_full_bit] == expected

def test_packet_get_fifo_full_flag():
    p = Packet()
    expected = 1
    p.fifo_full_flag = expected
    assert p.fifo_full_flag == expected

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

def test_packet_set_test_counter():
    p = Packet()
    p.test_counter = 18376
    expected = BitArray('uint:16=18376')
    result = (p.bits[Packet.test_counter_bits_15_12] +
            p.bits[Packet.test_counter_bits_11_0])
    assert result == expected

def test_packet_get_test_counter():
    p = Packet()
    expected = 19831
    p.test_counter = expected
    assert p.test_counter == expected

def test_configuration_set_pixel_trim_thresholds():
    c = Configuration()
    expected = [0x05] * Chip.num_channels
    c.pixel_trim_thresholds = expected
    assert c._pixel_trim_thresholds == expected
    expected[5] = 0x10
    c.pixel_trim_thresholds[5] = 0x10
    assert c._pixel_trim_thresholds == expected

def test_configuration_set_pixel_trim_thresholds_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: wrong num_channels'):
        c.pixel_trim_thresholds = [0x05] * (Chip.num_channels-1)
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.pixel_trim_thresholds = [0x20] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.pixel_trim_thresholds = [-10] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.pixel_trim_thresholds = 5

def test_configuration_get_pixel_trim_thresholds():
    c = Configuration()
    expected = [0x10] * Chip.num_channels
    c._pixel_trim_thresholds = expected
    assert c.pixel_trim_thresholds == expected

def test_configuration_set_global_threshold():
    c = Configuration()
    expected = 0x5a
    c.global_threshold = expected
    assert c._global_threshold == expected

def test_configuration_set_global_threshold_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.global_threshold = 0x100
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.global_threshold = -10
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.global_threshold = True

def test_configuration_get_global_threshold():
    c = Configuration()
    expected = 0x50
    c._global_threshold = expected
    assert c.global_threshold == expected

def test_configuration_set_csa_gain():
    c = Configuration()
    expected = 0
    c.csa_gain = expected
    assert c._csa_gain == expected

def test_configuration_set_csa_gain_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: invalid value'):
        c.csa_gain = 5
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.csa_gain = False

def test_configuration_get_csa_gain():
    c = Configuration()
    expected = 0
    c._csa_gain = expected
    assert c.csa_gain == expected

def test_configuration_set_csa_bypass():
    c = Configuration()
    expected = 0
    c.csa_bypass = expected
    assert c._csa_bypass == expected

def test_configuration_set_csa_bypass_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: invalid value'):
        c.csa_bypass = 5
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.csa_bypass = False

def test_configuration_get_csa_bypass():
    c = Configuration()
    expected = 0
    c._csa_bypass = expected
    assert c.csa_bypass == expected

def test_configuration_set_internal_bypass():
    c = Configuration()
    expected = 0
    c.internal_bypass = expected
    assert c._internal_bypass == expected

def test_configuration_set_internal_bypass_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: invalid value'):
        c.internal_bypass = 5
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.internal_bypass = False

def test_configuration_get_internal_bypass():
    c = Configuration()
    expected = 0
    c._internal_bypass = expected
    assert c.internal_bypass == expected

def test_configuration_set_csa_bypass_select():
    c = Configuration()
    expected = [0x1] * Chip.num_channels
    c.csa_bypass_select = expected
    assert c._csa_bypass_select == expected
    expected[5] = 0x0
    c.csa_bypass_select[5] = expected[5]
    assert c._csa_bypass_select == expected

def test_configuration_set_csa_bypass_select_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: wrong num_channels'):
        c.csa_bypass_select = [0x1] * (Chip.num_channels-1)
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.csa_bypass_select = [0x2] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.csa_bypass_select = [-1] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.csa_bypass_select = 5

def test_configuration_get_csa_bypass_select():
    c = Configuration()
    expected = [0x1] * Chip.num_channels
    c._csa_bypass_select = expected
    assert c.csa_bypass_select == expected

def test_configuration_set_csa_monitor_select():
    c = Configuration()
    expected = [0x0] * Chip.num_channels
    c.csa_monitor_select = expected
    assert c._csa_monitor_select == expected
    expected[5] = 0x1
    c.csa_monitor_select[5] = expected[5]
    assert c._csa_monitor_select == expected

def test_configuration_set_csa_monitor_select_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: wrong num_channels'):
        c.csa_monitor_select = [0x1] * (Chip.num_channels-1)
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.csa_monitor_select = [0x2] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.csa_monitor_select = [-1] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.csa_monitor_select = 5

def test_configuration_get_csa_monitor_select():
    c = Configuration()
    expected = [0x0] * Chip.num_channels
    c._csa_monitor_select = expected
    assert c.csa_monitor_select == expected

def test_configuration_set_csa_testpulse_enable():
    c = Configuration()
    expected = [0x1] * Chip.num_channels
    c.csa_testpulse_enable = expected
    assert c._csa_testpulse_enable == expected
    expected[5] = 0x0
    c.csa_testpulse_enable[5] = expected[5]
    assert c._csa_testpulse_enable == expected

def test_configuration_set_csa_testpulse_enable_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: wrong num_channels'):
        c.csa_testpulse_enable = [0x1] * (Chip.num_channels-1)
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.csa_testpulse_enable = [0x2] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.csa_testpulse_enable = [-1] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.csa_testpulse_enable = 5

def test_configuration_get_csa_testpulse_enable():
    c = Configuration()
    expected = [0x1] * Chip.num_channels
    c._csa_testpulse_enable = expected
    assert c.csa_testpulse_enable == expected

def test_configuration_set_csa_testpulse_dac_amplitude():
    c = Configuration()
    expected = 0x5a
    c.csa_testpulse_dac_amplitude = expected
    assert c._csa_testpulse_dac_amplitude == expected

def test_configuration_set_csa_testpulse_dac_amplitude_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.csa_testpulse_dac_amplitude = 0x100
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.csa_testpulse_dac_amplitude = -10
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.csa_testpulse_dac_amplitude = True

def test_configuration_get_csa_testpulse_dac_amplitude():
    c = Configuration()
    expected = 0x50
    c._csa_testpulse_dac_amplitude = expected
    assert c.csa_testpulse_dac_amplitude == expected

def test_configuration_set_test_mode():
    c = Configuration()
    expected = Configuration.TEST_UART
    c.test_mode = expected
    assert c._test_mode == expected

def test_configuration_set_test_mode_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: invalid value'):
        c.test_mode = 5
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.test_mode = False

def test_configuration_get_test_mode():
    c = Configuration()
    expected = Configuration.TEST_FIFO
    c._test_mode = expected
    assert c.test_mode == expected

def test_configuration_set_cross_trigger_mode():
    c = Configuration()
    expected = 0
    c.cross_trigger_mode = expected
    assert c._cross_trigger_mode == expected

def test_configuration_set_cross_trigger_mode_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: invalid value'):
        c.cross_trigger_mode = 5
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.cross_trigger_mode = False

def test_configuration_get_cross_trigger_mode():
    c = Configuration()
    expected = 0
    c._cross_trigger_mode = expected
    assert c.cross_trigger_mode == expected

def test_configuration_set_periodic_reset():
    c = Configuration()
    expected = 0
    c.periodic_reset = expected
    assert c._periodic_reset == expected

def test_configuration_set_periodic_reset_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: invalid value'):
        c.periodic_reset = 5
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.periodic_reset = False

def test_configuration_get_periodic_reset():
    c = Configuration()
    expected = 0
    c._periodic_reset = expected
    assert c.periodic_reset == expected

def test_configuration_set_fifo_diagnostic():
    c = Configuration()
    expected = 0
    c.fifo_diagnostic = expected
    assert c._fifo_diagnostic == expected

def test_configuration_set_fifo_diagnostic_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: invalid value'):
        c.fifo_diagnostic = 5
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.fifo_diagnostic = False

def test_configuration_get_fifo_diagnostic():
    c = Configuration()
    expected = 0
    c._fifo_diagnostic = expected
    assert c.fifo_diagnostic == expected

def test_configuration_set_test_burst_length():
    c = Configuration()
    expected = 0x125a
    c.test_burst_length = expected
    assert c._test_burst_length == expected

def test_configuration_set_test_burst_length_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.test_burst_length = 0x10000
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.test_burst_length = -10
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.test_burst_length = True

def test_configuration_get_test_burst_length():
    c = Configuration()
    expected = 0x502e
    c._test_burst_length = expected
    assert c.test_burst_length == expected

def test_configuration_set_adc_burst_length():
    c = Configuration()
    expected = 0x5a
    c.adc_burst_length = expected
    assert c._adc_burst_length == expected

def test_configuration_set_adc_burst_length_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.adc_burst_length = 0x100
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.adc_burst_length = -10
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.adc_burst_length = True

def test_configuration_get_adc_burst_length():
    c = Configuration()
    expected = 0x50
    c._adc_burst_length = expected
    assert c.adc_burst_length == expected

def test_configuration_set_channel_mask():
    c = Configuration()
    expected = [0x1] * Chip.num_channels
    c.channel_mask = expected
    assert c._channel_mask == expected
    expected[5] = 0x0
    c.channel_mask[5] = expected[5]
    assert c._channel_mask == expected

def test_configuration_set_channel_mask_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: wrong num_channels'):
        c.channel_mask = [0x1] * (Chip.num_channels-1)
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.channel_mask = [0x2] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.channel_mask = [-1] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.channel_mask = 5

def test_configuration_get_channel_mask():
    c = Configuration()
    expected = [0x1] * Chip.num_channels
    c._channel_mask = expected
    assert c.channel_mask == expected

def test_configuration_set_external_trigger_mask():
    c = Configuration()
    expected = [0x0] * Chip.num_channels
    c.external_trigger_mask = expected
    assert c._external_trigger_mask == expected
    expected[5] = 0x1
    c.external_trigger_mask[5] = expected[5]
    assert c._external_trigger_mask == expected

def test_configuration_set_external_trigger_mask_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: wrong num_channels'):
        c.external_trigger_mask = [0x1] * (Chip.num_channels-1)
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.external_trigger_mask = [0x2] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.external_trigger_mask = [-1] * Chip.num_channels
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.external_trigger_mask = 5

def test_configuration_get_external_trigger_mask():
    c = Configuration()
    expected = [0x0] * Chip.num_channels
    c._external_trigger_mask = expected
    assert c.external_trigger_mask == expected

def test_configuration_set_reset_cycles():
    c = Configuration()
    expected = 0x125abc
    c.reset_cycles = expected
    assert c._reset_cycles == expected

def test_configuration_set_reset_cycles_errors():
    c = Configuration()
    with pytest.raises(ValueError, message='Should fail: value too large'):
        c.reset_cycles = 0x1000000
    with pytest.raises(ValueError, message='Should fail: value negative'):
        c.reset_cycles = -10
    with pytest.raises(ValueError, message='Should fail: wrong type'):
        c.reset_cycles = True

def test_configuration_get_reset_cycles():
    c = Configuration()
    expected = 0x502ef2
    c._reset_cycles = expected
    assert c.reset_cycles == expected

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

def test_configuration_to_dict():
    c = Configuration()
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

def test_configuration_from_dict():
    c = Configuration()
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
    assert result == expected

def test_configuration_write_errors(tmpdir):
    c = Configuration()
    f = tmpdir.join('test_config.json')
    f.write("Test data.....")
    with pytest.raises(IOError, message='Should fail: force fails'):
        c.write(str(f))

def test_configuration_write_force(tmpdir):
    c = Configuration()
    f = tmpdir.join('test_config.json')
    f.write("Test data.....")
    c.write(str(f), force=True)
    with open(str(f), 'r') as output:
        result = json.load(output)
    expected = c.to_dict()
    assert result == expected

def test_configuration_read(tmpdir):
    c = Configuration()
    c.pixel_trim_thresholds[0] = 30
    c.reset_cycles = 0x100010
    f = str(tmpdir.join('test_config.json'))
    c.write(f)
    c2 = Configuration()
    c2.load(f)
    expected = c.to_dict()
    result = c2.to_dict()
    assert result == expected

def test_configuration_read_default():
    c = Configuration()
    expected = c.to_dict()
    c.global_threshold = 100
    c.load('default.json')
    result = c.to_dict()
    assert result == expected

def test_controller_get_chip():
    controller = Controller(None)
    chip = Chip(1, 3)
    controller.chips.append(chip)
    assert controller.get_chip(1, 3) == chip

def test_controller_get_chip_error():
    controller = Controller(None)
    chip = Chip(1, 3)
    controller.chips.append(chip)
    with pytest.raises(ValueError, message='Should fail: bad chipid'):
        controller.get_chip(0, 3)
    with pytest.raises(ValueError, message='Should fail: bad chainid'):
        controller.get_chip(1, 1)

def test_controller_serial_read_mock():
    controller = Controller(None)
    controller._serial = MockSerialPort
    MockSerialPort.data_to_mock_read = bytes(bytearray(10))
    result = controller.serial_read(0.1)
    expected = bytes(bytearray(10))
    assert result == expected

def test_controller_serial_write_mock(capfd):
    controller = Controller(None)
    controller._serial = MockSerialPort
    to_write = [b's12345678q', b's87654321q']
    controller.serial_write(to_write)
    result, err = capfd.readouterr()
    expected = ''.join(map(bytes2str, to_write))
    assert result == expected

def test_controller_serial_write_read_mock(capfd):
    controller = Controller(None)
    controller._serial = MockSerialPort
    to_write = [b's12345678q', b's9862983aq']
    MockSerialPort.data_to_mock_read = bytes(bytearray(range(256)))
    read_result = controller.serial_write_read(to_write, 0.1)
    write_result, err = capfd.readouterr()
    read_expected = bytes(bytearray(range(256)))
    write_expected = ''.join(map(bytes2str, to_write))
    assert read_result == read_expected
    assert write_result == write_expected

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

def test_controller_write_configuration(capfd):
    controller = Controller(None)
    controller._test_mode = True
    controller._serial = MockSerialPort
    chip = Chip(2, 4)
    result = controller.write_configuration(chip)
    assert result == b''
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)
    expected = ' '.join(map(bytes2str, [controller.format_UART(chip, conf_data_i) for
            conf_data_i in conf_data]))
    result, err = capfd.readouterr()
    assert result == expected

def test_controller_write_configuration_one_reg(capfd):
    controller = Controller(None)
    controller._test_mode = True
    controller._serial = MockSerialPort
    chip = Chip(2, 4)
    result = controller.write_configuration(chip, 0)
    assert result == b''
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)[0]
    expected = bytes2str(controller.format_UART(chip, conf_data))
    result, err = capfd.readouterr()
    assert result == expected

def test_controller_write_configuration_write_read(capfd):
    controller = Controller(None)
    controller._serial = MockSerialPort
    controller.timeout=0.01
    chip = Chip(2, 4)
    to_read = b's12345678q'
    MockSerialPort.data_to_mock_read = to_read
    result = controller.write_configuration(chip, registers=5, write_read=0.1)
    assert result == to_read
    conf_data = chip.get_configuration_packets(Packet.CONFIG_WRITE_PACKET)[5]
    expected = bytes2str(controller.format_UART(chip, conf_data))
    result, err = capfd.readouterr()
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
