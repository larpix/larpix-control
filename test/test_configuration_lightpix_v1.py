from larpix import Configuration_Lightpix_v1
from bitarray import bitarray
import larpix.bitarrayhelper as bah
from larpix import configs
import json

def test_conf_all_registers():
    default_filename = 'chip/default_lightpix_v1.json'
    data = configs.load(default_filename)

    c = Configuration_Lightpix_v1()
    print(data, len(data))
    print(c.register_names,len(c.register_names))
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
    c = Configuration_Lightpix_v1()
    endian = 'little'

    # test simple register
    c.timeout = 12
    assert c.timeout == 12
    assert c.timeout_data == [(238, bah.fromuint(12,8, endian=endian))]

    c.timeout_data = (238, bah.fromuint(90,8, endian=endian))
    assert c.timeout == 90
    assert c.timeout_data == [(238, bah.fromuint(90,8, endian=endian))]

    c.timeout_data = bah.fromuint(34,8, endian=endian)
    assert c.timeout == 34
    assert c.timeout_data == [(238, bah.fromuint(34,8, endian=endian))]

    # test compound register
    c.lightpix_mode = 1
    c.hit_threshold = 3
    reg_data = [(237, bitarray('11100000'))]
    assert c.lightpix_mode == 1
    assert c.lightpix_mode_data == reg_data
    assert c.hit_threshold == 3
    assert c.hit_threshold_data == reg_data

    c.hit_threshold = 0
    reg_data = [(237, bitarray('10000000'))]
    assert c.lightpix_mode == 1
    assert c.lightpix_mode_data == reg_data
    assert c.hit_threshold == 0
    assert c.hit_threshold_data == reg_data

def test_compare():
    c = Configuration_Lightpix_v1()
    other = Configuration_Lightpix_v1()
    assert c.compare(other) == {}

    c.lightpix_mode = 1
    other.lightpix_mode = 0
    assert c.compare(other) == {'lightpix_mode': (1,0)}

def test_get_nondefault_registers():
    c = Configuration_Lightpix_v1()
    c.lightpix_mode = 1
    c.hit_threshold = 8
    c.timeout = 34
    assert c.get_nondefault_registers() == {
            'lightpix_mode': (1,0),
            'hit_threshold': (8,16),
            'timeout': (34, 30)
            }
