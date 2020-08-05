import pytest
import json

from larpix import Controller, Configuration_v2, Key
from larpix.io import FakeIO

@pytest.fixture
def network_config_old(tmpdir):
    '''
    Defines a network of:
        MISO_US:
            3       13
            ^       ^
            2   >   12

        MISO_DS:
            3       13
            v       v
            2   <   12
            v

    '''
    filename = str(tmpdir.join('test_network_conf_old.json'))
    config_dict = {
        "_config_type": "controller",
        "name": "test",
        "asic_version": 2,
        "network": {
            "1": {
                "1": {
                    "nodes": [
                        {
                            "chip_id": "ext",
                            "root": True,
                            "miso_us": [2, None, None, None]
                        },
                        {
                            "chip_id": 2,
                            "miso_us": [3, None, None, 12],
                        },
                        {
                            "chip_id": 3
                        },
                        {
                            "chip_id": 12,
                            "miso_us": [13, None, None, None]
                        },
                        {
                            "chip_id": 13
                        }
                    ],
                }
            },
            "miso_us_uart_map": [0,1,2,3],
            "miso_ds_uart_map": [2,3,0,1],
            "mosi_uart_map": [2,3,0,1]
        }
    }
    with open(filename,'w') as of:
        json.dump(config_dict, of)
    return filename

@pytest.fixture
def network_config_new(tmpdir, network_config_old):
    filename = str(tmpdir.join('test_network_conf_new.json'))
    with open(network_config_old,'r') as f:
        d = json.load(f)
    del d['network']['miso_us_uart_map']
    del d['network']['miso_ds_uart_map']
    del d['network']['mosi_uart_map']

    d['network']['miso_uart_map'] = [0,1,2,3]
    d['network']['mosi_uart_map'] = [0,1,2,3]
    d['network']['usds_link_map'] = [2,3,0,1]
    with open(filename,'w') as of:
        json.dump(d, of)
    return filename

@pytest.fixture
def inheriting_network_config(tmpdir, network_config_old):
    filename = str(tmpdir.join('other_test_network_conf.json'))
    config_dict = {
        "_config_type": "controller",
        "_include": [network_config_old],
        "name": "other_test",
        "network": {
            "1": {
                "2": {
                    "nodes": [
                        {
                            "chip_id": "ext",
                            "root": True,
                            "miso_us": [None, None, 123, None]
                        },
                        {
                            "chip_id": 123,
                        }
                    ],
                    "miso_us_uart_map": [0,1,2,3],
                    "miso_ds_uart_map": [2,3,0,1],
                }
            },
        }
    }
    with open(filename,'w') as of:
        json.dump(config_dict, of)
    return filename

@pytest.fixture
def network_controller_old(network_config_old):
    c = Controller()
    c.load(network_config_old)
    c.io = FakeIO()
    return c

@pytest.fixture
def network_controller_new(network_config_new):
    c = Controller()
    c.load(network_config_new)
    c.io = FakeIO()
    return c

def test_controller_network(network_controller_old, network_controller_new):
    for c in (network_controller_old, network_controller_new):
        networks = ('miso_us','miso_ds','mosi')
        for chip_key in c.chips:
            for network in networks:
                assert chip_key.chip_id in c.network[chip_key.io_group][chip_key.io_channel][network].nodes()
        us_links = [('ext',2),(2,3),(2,12),(12,13)]
        ds_links = [(3,2),(12,2),(13,12),(2,'ext')]
        mosi_links = [link[::-1] for link in us_links] + [link[::-1] for link in ds_links]
        assert set(c.network[chip_key.io_group][chip_key.io_channel]['miso_us'].edges()) == set(us_links)
        assert set(c.network[chip_key.io_group][chip_key.io_channel]['miso_ds'].edges()) == set(ds_links)
        assert set(c.network[chip_key.io_group][chip_key.io_channel]['mosi'].edges()) == set(mosi_links)

        c.remove_chip('1-1-3')
        assert len(c.chips) == 3
        assert len(c.network[1][1]['miso_us'].edges()) == 3
        assert len(c.network[1][1]['miso_ds'].edges()) == 3
        assert len(c.network[1][1]['mosi'].edges()) == 6
        assert not any(3 in c.network[1][1][network] for network in networks)

        c.add_chip('1-1-3')
        assert len(c.chips) == 4
        assert len(c.network[1][1]['miso_us'].nodes()) == 5
        assert len(c.network[1][1]['miso_ds'].nodes()) == 5
        assert len(c.network[1][1]['mosi'].nodes()) == 5
        assert all(3 in c.network[1][1][network] for network in networks)

        c.add_network_link(1,1,'miso_us',(2,3),0)
        assert len(c.network[1][1]['miso_us'].edges()) == 4
        assert c.network[1][1]['miso_us'].edges[(2,3)]['uart'] == 0
        c.add_network_link(1,1,'miso_ds',(3,2),2)
        assert len(c.network[1][1]['miso_ds'].edges()) == 4
        assert c.network[1][1]['miso_ds'].edges[(3,2)]['uart'] == 2
        c.add_network_link(1,1,'mosi',(3,2),0)
        c.add_network_link(1,1,'mosi',(2,3),2)
        assert len(c.network[1][1]['mosi'].edges()) == 8
        assert c.network[1][1]['mosi'].edges[(3,2)]['uart'] == 0
        assert c.network[1][1]['mosi'].edges[(2,3)]['uart'] == 2

def test_controller_inherit_config(inheriting_network_config):
    c = Controller()
    c.load(inheriting_network_config)

    assert len(c.chips) == 5
    assert len(c.network[1][1]['mosi'].nodes) == 5
    assert len(c.network[1][2]['mosi'].nodes) == 2

def test_controller_init(network_controller_old, network_controller_new):
    for c in (network_controller_old, network_controller_new):
        assert len(c.chips) == 4
        assert len(c.network[1][1]) == 3
        assert len(c.network[1][1]['miso_us'].edges()) == 4
        assert len(c.network[1][1]['miso_ds'].edges()) == 4
        assert len(c.network[1][1]['mosi'].edges()) == 8
        assert ('ext', 2) in c.network[1][1]['mosi'].in_edges(2)

        c.init_network(1,1,2)
        assert c['1-1-2'].config.chip_id == 2
        assert c['1-1-2'].config.enable_miso_upstream == [0,0,0,0]
        assert c['1-1-2'].config.enable_miso_downstream == [0,0,1,0]
        assert c['1-1-2'].config.enable_mosi == [1,0,1,1]

        c.init_network(1,1,3)
        assert c['1-1-2'].config.enable_miso_upstream == [1,0,0,0]
        assert c['1-1-3'].config.chip_id == 3
        assert c['1-1-3'].config.enable_miso_upstream == [0,0,0,0]
        assert c['1-1-3'].config.enable_miso_downstream == [0,0,1,0]
        assert c['1-1-3'].config.enable_mosi == [0,0,1,0]
        assert c.io.sent[-1][-1] == c['1-1-3'].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_mosi'])[0]
        assert c.io.sent[-1][-2] == c['1-1-3'].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_miso_downstream'])[0]
        chip_id_config_packet = c['1-1-3'].get_configuration_write_packets(registers=Configuration_v2.register_map['chip_id'])[0]
        chip_id_config_packet.chip_id = 1
        assert c.io.sent[-1][-3] == chip_id_config_packet
        assert c.io.sent[-1][-4] == c['1-1-2'].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_miso_upstream'])[0]

        c.init_network(1,1)
        assert c['1-1-2'].config.chip_id == 2
        assert c['1-1-2'].config.enable_miso_downstream == [0,0,1,0]
        assert c['1-1-2'].config.enable_mosi == [1,0,1,1]
        assert c['1-1-2'].config.enable_miso_upstream == [1,0,0,1]
        assert c['1-1-3'].config.chip_id == 3
        assert c['1-1-3'].config.enable_miso_upstream == [0,0,0,0]
        assert c['1-1-3'].config.enable_miso_downstream == [0,0,1,0]
        assert c['1-1-3'].config.enable_mosi == [0,0,1,0]
        assert c['1-1-12'].config.chip_id == 12
        assert c['1-1-12'].config.enable_miso_upstream == [1,0,0,0]
        assert c['1-1-12'].config.enable_miso_downstream == [0,1,0,0]
        assert c['1-1-12'].config.enable_mosi == [1,1,0,0]
        assert c['1-1-13'].config.chip_id == 13
        assert c['1-1-13'].config.enable_miso_upstream == [0,0,0,0]
        assert c['1-1-13'].config.enable_miso_downstream == [0,0,1,0]
        assert c['1-1-13'].config.enable_mosi == [0,0,1,0]

def test_controller_init_complete(network_controller_old, network_controller_new):
    for c in (network_controller_old, network_controller_new):
        c.init_network(1,1)
        assert c['1-1-2'].config.chip_id == 2
        assert c['1-1-2'].config.enable_miso_downstream == [0,0,1,0]
        assert c['1-1-2'].config.enable_mosi == [1,0,1,1]
        assert c['1-1-2'].config.enable_miso_upstream == [1,0,0,1]
        assert c['1-1-3'].config.chip_id == 3
        assert c['1-1-3'].config.enable_miso_upstream == [0,0,0,0]
        assert c['1-1-3'].config.enable_miso_downstream == [0,0,1,0]
        assert c['1-1-3'].config.enable_mosi == [0,0,1,0]
        assert c['1-1-12'].config.chip_id == 12
        assert c['1-1-12'].config.enable_miso_upstream == [1,0,0,0]
        assert c['1-1-12'].config.enable_miso_downstream == [0,1,0,0]
        assert c['1-1-12'].config.enable_mosi == [1,1,0,0]
        assert c['1-1-13'].config.chip_id == 13
        assert c['1-1-13'].config.enable_miso_upstream == [0,0,0,0]
        assert c['1-1-13'].config.enable_miso_downstream == [0,0,1,0]
        assert c['1-1-13'].config.enable_mosi == [0,0,1,0]

def test_controller_reset(network_controller_old, network_controller_new):
    for c in (network_controller_old, network_controller_new):
        c.init_network(1,1)

        c.reset_network(1,1,13)
        assert c['1-1-13'].config.chip_id == 1
        assert c['1-1-13'].config.enable_miso_upstream == [0,0,0,0]
        assert c['1-1-13'].config.enable_miso_downstream == [0,0,0,0]
        assert c['1-1-13'].config.enable_mosi == [1,1,1,1]
        assert c.io.sent[-1][-4] == c['1-1-13'].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_mosi'])[0]
        assert c.io.sent[-1][-3] == c['1-1-13'].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_miso_downstream'])[0]
        chip_id_config_packet = c['1-1-13'].get_configuration_write_packets(registers=Configuration_v2.register_map['chip_id'])[0]
        chip_id_config_packet.chip_id = 13
        assert c.io.sent[-1][-2] == chip_id_config_packet
        assert c.io.sent[-1][-1] == c['1-1-12'].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_miso_upstream'])[0]

        c.reset_network(1,1)
        for chip_key in c.chips:
            print(chip_key)
            assert c[chip_key].config.enable_miso_upstream == [0,0,0,0]
            assert c[chip_key].config.chip_id == 1
            assert c[chip_key].config.enable_miso_downstream == [0,0,0,0]
            assert c[chip_key].config.enable_mosi == [1,1,1,1]

def test_controller_network_traversal(network_controller_old, network_controller_new):
    for c in (network_controller_old, network_controller_new):
        c = network_controller_new

        keys = c.get_network_keys(1,1,root_first_traversal=True)
        assert len(keys) == 4
        assert keys[0] == '1-1-2'
        assert set(keys[1:3]) == set(['1-1-3','1-1-12'])
        assert keys[3] == '1-1-13'

        keys = c.get_network_keys(1,1,root_first_traversal=False)
        assert len(keys) == 4
        assert keys[0] == '1-1-13'
        assert set(keys[1:3]) == set(['1-1-3','1-1-12'])
        assert keys[3] == '1-1-2'

