from bitarray import bitarray
import os
import errno
import functools
from collections import OrderedDict

from .. import bitarrayhelper as bah
from .. import configs

__all__ = [
    'BaseConfiguration',
    '_Smart_List',
]

class _Smart_List(list):
    '''
    A list type which checks its elements to be within given bounds.
    Used for Configuration attributes where there's a distinct value for
    each LArPix channel.

    '''

    def __init__(self, values, low, high):
        if not (type(values) == list or type(values) == _Smart_List):
            raise ValueError("_Smart_List is not list")
        if any([value > high or value < low for value in values]):
            raise ValueError("value out of bounds")
        list.__init__(self, values)
        self.low = low
        self.high = high

    def __setitem__(self, key, value):
        if isinstance(key, int):
            if value > self.high or value < self.low:
                raise ValueError("value out of bounds")
            list.__setitem__(self, key, value)
        else:
            for num in value:
                if num > self.high or num < self.low:
                    raise ValueError("value out of bounds")
            list.__setitem__(self, key, value)

    def __setslice__(self, i, j, value):
        '''
        Only used in Python 2, where __setslice__ is deprecated but
        contaminates the namespace of this subclass.

        '''
        self.__setitem__(slice(i, j, None), value)

def _nice_json(d, depth=1):
    '''
    Helper method for printing dicts in a dense but readable format for json

    '''
    l = []
    for key,value in d.items():
        if isinstance(value,str):
            l += ['\"{}\": \"{}\"'.format(key,value)]
        elif isinstance(value,dict):
            l += ['\"{}\": {}'.format(key, _nice_json(value, depth+1))]
        elif isinstance(value,bool):
            if value:
                l += ['\"{}\": true'.format(key)]
            else:
                l += ['\"{}\": false'.format(key)]
        elif value is None:
            l += ['\"{}\": null'.format(key)]
        else:
            l += ['\"{}\": {}'.format(key,value)]
    return '{\n'+depth*'    ' + (',\n'+depth*'    ').join(l) + '\n' +(depth-1)*'    '+'}'


class BaseConfiguration(object):
    '''
    Base class for larpix configuration objects

    '''

    def __init__(self):
        self.load(self.default_configuration_file)

    def __setattr__(self, name, value):
        '''
        Default setattr behavior occurs if name is in ``register_names``, is "private"
        or is a known attribute
        Otherwise raises an attribute error

        '''
        # print('SET', name, value)
        if not (name in self.register_names or name[0] == '_' or hasattr(self, name)):
            raise AttributeError('%s is not a known register' % name)
        return super(BaseConfiguration, self).__setattr__(name, value)

    def __eq__(self, other):
        '''
        Returns true if all fields match
        '''
        return all([getattr(self, register_name) == getattr(other, register_name)
                    for register_name in self.register_names])

    def __str__(self):
        '''
        Converts configuration to a nicely formatted json string

        '''
        d = self.to_dict()
        return _nice_json(d)

    def compare(self, other):
        '''
        Returns a dict containing pairs of each differently valued register
        Pair order is (self, other)
        '''
        d = {}
        for register_name in self.register_names:
            if getattr(self, register_name) != getattr(other, register_name):
                d[register_name] = (getattr(self, register_name), getattr(other,
                    register_name))
        # Attempt to simplify some of the long values (array values)
        for (name, (self_value, config_value)) in d.items():
            if isinstance(self_value,(list,_Smart_List)):
                different_values = []
                for ch, (val, config_val) in enumerate(zip(self_value, config_value)):
                    if val != config_val:
                        different_values.append(({'index': ch, 'value': val},
                                                 {'index': ch, 'value': config_val}))
                if len(different_values) < 5:
                    d[name] = different_values
                else:
                    pass
        return d

    def get_nondefault_registers(self):
        '''
        Return a dict of all registers that are not set to the default
        configuration (i.e. of the ASIC on power-up). The keys are the
        register name where there's a difference, and the values are
        tuples of (current, default) configuration values.

        '''
        return self.compare(self.__class__())

    def to_dict(self):
        '''
        Export the configuration register names and values into a dict.

        '''
        d = {}
        for register_name in self.register_names:
            d[register_name] = getattr(self, register_name)
        return d

    def from_dict(self, d):
        '''
        Use a dict of ``{register_name, value}`` to update the current
        configuration. Not all registers must be in the dict - only
        those present will be updated.

        '''
        for register_name in self.register_names:
            if register_name in d:
                setattr(self, register_name, d[register_name])

    def write(self, filename, force=False, append=False):
        '''
        Save the configuration to a JSON file.

        '''
        if os.path.isfile(filename):
            if not force:
                raise IOError(errno.EEXIST,
                              'File %s exists. Use force=True to overwrite'
                              % filename)
        d = {
            '_config_type': 'chip',
            'class': self.__class__.__name__,
            'register_values': self.to_dict()
        }
        with open(filename, 'w+') as outfile:
            outfile.write(_nice_json(d))
        return 0

    def load(self, filename):
        '''
        Load a JSON file and use the contents to update the current
        configuration.

        '''
        data = configs.load(filename, 'chip')
        if data['class'] != self.__class__.__name__:
            raise RuntimeError('Configuration is not of class {}'.format(data['class']))
        self.from_dict(data['register_values'])
