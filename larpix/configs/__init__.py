import json
import os

def _load_and_verify(file, config_type=None):
    '''
    Checks that configuration type matches type requested

    '''
    config_data = json.load(file)
    if config_type:
        assert config_data['_config_type'] == config_type, "Invalid config type {}".format(config_data['_config_type'])
    return config_data

def load(filename, config_type=None):
    '''
    Load the specified configuration file.

    The path is first searched relative to the "current directory".
    If no match is found, the path is searched relative to the "config"
    package directory (aka ``__file__`` directly in code).

    '''
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            return _load_and_verify(f, config_type)
    elif os.path.isfile(os.path.join(os.path.dirname(__file__), filename)):
        with open(os.path.join(os.path.dirname(__file__), filename), 'r') as f:
            return _load_and_verify(f, config_type)
    else:
        raise IOError('File not found: %s' % filename)
