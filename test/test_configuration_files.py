import pytest
import json
from larpix import configs

@pytest.fixture
def tmpfile(tmpdir):
    return str(tmpdir.join('test_conf.json'))

@pytest.fixture
def other_tmpfile(tmpdir):
    return str(tmpdir.join('other_test_conf.json'))

@pytest.fixture
def other_other_tmpfile(tmpdir):
    return str(tmpdir.join('other_other_test_conf.json'))

def write_json(file, **kwargs):
    with open(file,'w') as of:
        json.dump(kwargs, of)

def test_config_read(tmpfile):
    write_json(tmpfile,
        _config_type='test',
        test=True
        )

    config = configs.load(tmpfile, 'test')
    assert config['_config_type'] == 'test'
    assert config['test']

    config = configs.load(tmpfile)
    assert config['_config_type'] == 'test'
    assert config['test']

    with pytest.raises(AssertionError):
        config = configs.load(tmpfile, 'not_test')

def test_config_inheritance(tmpfile, other_tmpfile):
    write_json(tmpfile,
        _config_type='test',
        _include=[other_tmpfile],
        test=True
        )
    write_json(other_tmpfile,
        _config_type='test',
        inherited=True
        )

    config = configs.load(tmpfile, 'test')
    assert config['inherited']
    assert config['test']

    write_json(tmpfile,
        _config_type='test',
        _include=[other_tmpfile],
        test=True
        )
    write_json(other_tmpfile,
        _config_type='test',
        test=False
        )

    config = configs.load(tmpfile, 'test')
    assert config['test']

def test_config_inheritance_complex(tmpfile, other_tmpfile):
    write_json(tmpfile,
        _config_type='test',
        _include=[other_tmpfile],
        dict_field={'base':True,'dict':{'overwrite':True}},
        list_field=[1]
        )
    write_json(other_tmpfile,
        _config_type='test',
        dict_field={'inherited':True,'base':False,'dict':{'test':True,'overwrite':False}},
        list_field=[2]
        )
    config = configs.load(tmpfile)
    assert config['dict_field']['base']
    assert config['dict_field']['inherited']
    assert config['dict_field']['dict']['test']
    assert config['dict_field']['dict']['overwrite']
    assert config['list_field'] == [1]

def test_config_inheritance_order(tmpfile, other_tmpfile, other_other_tmpfile):
    write_json(tmpfile,
        _config_type='test',
        _include=[other_tmpfile, other_other_tmpfile]
        )
    write_json(other_tmpfile,
        _config_type='test',
        test=1
        )
    write_json(other_other_tmpfile,
        _config_type='test',
        test=2
        )

    config = configs.load(tmpfile)
    assert config['test'] == 2

def test_config_inheritance_error(tmpfile, other_tmpfile):
    write_json(tmpfile,
        _config_type='test',
        _include=[other_tmpfile]
        )
    write_json(other_tmpfile,
        _config_type='not_test'
        )

    with pytest.raises(AssertionError):
        config = configs.load(tmpfile, 'test')

    with pytest.raises(AssertionError):
        config = configs.load(tmpfile)
