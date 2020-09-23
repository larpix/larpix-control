from bitarray import bitarray
import os
import errno
import functools
from collections import OrderedDict

from .. import bitarrayhelper as bah
from .. import configs
from . import Configuration_v2, _Smart_List
from . import configuration_v2 as conf_v2

class Configuration_Lightpix_v1(Configuration_v2):
    '''
    Represents the desired configuration state of a LightPix v1 chip.

    This is a small extension of the LArPix v2 configuration register space to
    include the additional registers associated with LightPix, see the v2
    configuration class for a more detailed description of the implementation.

    '''

    asic_version = 'lightpix-v1.0'
    default_configuration_file = 'chip/default_lightpix_v1.json'
    num_registers = 239
    num_bits = 1912
    # Additional class properties regarding configuration registers are set at the end of the file.

    def __init__(self):
        # Note: properties, getters and setters are constructed after this class definition at the bottom of the file.
        super(Configuration_Lightpix_v1, self).__init__()
        return

## Set up property info
#
_property_configuration = OrderedDict([
        ('lightpix_mode',
            (conf_v2._compound_property, (['lightpix_mode','hit_threshold'], (int,bool), 0, 1), (1896, 1897))),
        ('hit_threshold',
            (conf_v2._compound_property, (['lightpix_mode','hit_threshold'], int, 0, 127), (1897, 1904))),
        ('timeout',
            (conf_v2._basic_property, (int, 0, 255), (1904, 1912))),
    ])
_property_configuration.update(conf_v2._property_configuration)

# GENERATE THE PROPERTIES!
Configuration_Lightpix_v1.bit_map = OrderedDict()
Configuration_Lightpix_v1.register_map = OrderedDict()
Configuration_Lightpix_v1.register_names = []
conf_v2._generate_properties(Configuration_Lightpix_v1, _property_configuration, verbose=False)
