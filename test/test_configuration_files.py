import pytest
import json
from larpix import configs

@pytest.fixture
def tmpfile(tmpdir):
    return str(tmpdir.join('test_conf.json'))

@pytest.fixture
def other_tmpfile(tmpdir):
    return str(tmpdir.join('other_test_conf.json'))

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
