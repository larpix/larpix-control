'''
A module to control the LArPix chip.

'''

from __future__ import absolute_import
from __future__ import print_function
import time
import json
import os
import errno
import math
import warnings
import struct
import sys
from collections import OrderedDict

from bitarray import bitarray

from . import bitarrayhelper as bah

from .key import *
from .chip import *
from .configuration import *
from .configuration import _Smart_List
from .controller import *
from .packet import *

from .logger import Logger
from . import configs
