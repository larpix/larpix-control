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
from .logger import Logger
from . import configs
from .key import Key
from .chip import Chip
from .configuration import Configuration, _Smart_List
from .controller import Controller
from .packet import TimestampPacket, MessagePacket, Packet, PacketCollection

warnings.filterwarnings('default', category=ImportWarning)
warnings.warn('larpix.larpix module has been refactored into sub-modules',ImportWarning)

