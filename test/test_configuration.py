from larpix import Configuration_v2
from bitarray import bitarray
import larpix.bitarrayhelper as bah
from larpix import configs
import json

def test_v2_conf_all_registers():
    default_filename = 'chip/default_v2.json'
    data = configs.load(default_filename)

    c = Configuration_v2()
    # check that all registers are in the configuration file
    assert set(data['register_values'].keys()) == set(c.register_names)
    for register in c.register_names:
        print('testing {}'.format(register))
        config_value = data['register_values'][register]
        stored_value = getattr(c,register)

        # test getters
        assert stored_value == config_value

        # test setters
        if register == 'chip_id':
            new_value = 12
        elif isinstance(stored_value, list):
            new_value = []
            for value in stored_value:
                if value == 1:
                    new_value += [0]
                elif value == 0:
                    new_value += [1]
                else:
                    new_value += [value-1]
        elif isinstance(stored_value, int):
            if stored_value == 1:
                new_value = 0
            elif stored_value == 0:
                new_value = 1
            else:
                new_value = stored_value-1
        setattr(c,register,new_value)
        assert getattr(c,register) == new_value

        # test data getters
        assert list(c.register_map[register]) == [reg for reg,bits in getattr(c,register+'_data')]

def test_conf():
    c = Configuration_v2()
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

    # test compound list register (that covers <1 register)
    c.enable_miso_downstream = [0]*4
    c.enable_miso_differential = [0]*4
    assert c.enable_miso_differential == [0]*4
    assert c.enable_miso_differential_data == [(125, bah.fromuint(0,8, endian=endian))]

    c.enable_miso_differential[1] = 1
    assert c.enable_miso_differential[1] == 1
    assert c.enable_miso_differential[0] == 0
    assert c.enable_miso_differential_data == [(125, bitarray('00000100'))]

    c.enable_miso_differential_data = (125, bitarray('00000010'))
    assert c.enable_miso_differential[1] == 0
    assert c.enable_miso_differential[2] == 1
    assert c.enable_miso_differential_data == [(125, bitarray('00000010'))]

    bits = bitarray('0100')
    c.enable_miso_differential_data = bits
    assert c.enable_miso_differential[1] == 1
    assert c.enable_miso_differential[0] == 0
    assert c.enable_miso_differential_data == [(125, bitarray('00000100'))]

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

def test_compare():
    c = Configuration_v2()
    other = Configuration_v2()
    assert c.compare(other) == {}

    c.pixel_trim_dac[10] = 25
    c.pixel_trim_dac[12] = 26
    assert c.compare(other) == {'pixel_trim_dac': [
        ({'index': 10, 'value': 25}, {'index': 10, 'value': 16}),
        ({'index': 12, 'value': 26}, {'index': 12, 'value': 16}),
        ]}

    c = Configuration_v2()
    c.threshold_global = 121
    assert c.compare(other) == {'threshold_global': (121, 255)}

def test_load_inheritance(tmpdir):
    filename = 'test.json'
    c = Configuration_v2()
    with open(str(tmpdir.join(filename)),'w') as of:
        config = {
            "_config_type": "chip",
            "_include": ["chip/default_v2.json"],
            "class": "Configuration_v2",
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

def test_get_nondefault_registers():
    c = Configuration_v2()
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
