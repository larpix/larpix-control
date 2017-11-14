import json
import os

def load(filename):
    '''
    Load the specified configuration file.

    The path is first searched relative to the "current directory".
    If no match is found, the path is searched relative to the "config"
    package directory (aka ``__file__`` directly in code).

    '''
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    elif os.path.isfile(os.path.join(os.path.dirname(__file__), filename)):
        with open(os.path.join(os.path.dirname(__file__), filename), 'r') as f:
            return json.load(f)
    else:
        raise IOError('File not found: %s' % filename)
