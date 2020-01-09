import json
import os

def _load_and_verify(file, config_type=None):
    '''
    Loads full inheritance and checks that configuration type matches type requested

    '''
    config_data = json.load(file)
    if config_type:
        assert config_data['_config_type'] == config_type, "Invalid config type {}".format(config_data['_config_type'])
    return _load_inheritance(config_data)

def _inherit_dict(d, other, config_type=None):
    '''
    Copies other and overwrites with values from d following inheritance rules
    of the config_type

    '''
    combined_d = dict(other.items())
    for key,val in d.items():
        if isinstance(val, dict) and key in other:
            combined_d[key] = _inherit_dict(val, other[key], config_type)
        else:
            combined_d[key] = val
    return combined_d

def _load_inheritance(config):
    '''
    Loads parent config files specified in the "_include" field of a
    configuration.

    All files must be of the same config type and are loaded in the order
    specified in the list.

    All fields of dict-like objects within the included fields will be inherited
    recursively

    '''

    if not '_include' in config:
        return config

    base_config = dict()
    if not isinstance(config['_include'],list):
        raise RuntimeError('inherited files not specified as list')
    config_type = None
    if '_config_type' in config:
        config_type = config['_config_type']
    for included_file in config['_include']:
        inherited_config = load(included_file, config_type=config_type)
        for key,val in inherited_config.items():
            if isinstance(val, dict) and key in base_config:
                base_config[key] = _inherit_dict(val, base_config[key], config_type)
            else:
                base_config[key] = val
    for key,val in config.items():
        if isinstance(val, dict) and key in base_config:
            base_config[key] = _inherit_dict(val, base_config[key], config_type)
        else:
            base_config[key] = val
    return base_config

def load(filename, config_type=None):
    '''
    Load the specified configuration file.

    The path is first searched relative to the "current directory".
    If no match is found, the path is searched relative to the "config"
    package directory (aka ``__file__`` directly in code).

    '''
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            data = _load_and_verify(f, config_type)
            return data
    elif os.path.isfile(os.path.join(os.path.dirname(__file__), filename)):
        with open(os.path.join(os.path.dirname(__file__), filename), 'r') as f:
            return _load_and_verify(f, config_type)
    else:
        raise IOError('File not found: %s' % filename)
