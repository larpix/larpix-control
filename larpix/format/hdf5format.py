'''
This module gives access to the LArPix+HDF5 file format.

File format description
=======================

All LArPix+HDF5 files use the HDF5 format so that they
can be read and written using any language that has an HDF5 binding. The
documentation for the Python h5py binding is at <http://docs.h5py.org>.

The ``to_file`` and ``from_file`` methods translate between a list of
Packet-like objects and an HDF5 data file. ``from_file`` can be used to
load up the full file all at once or just a subset of rows (supposing
the full file was too big to fit in memory). To access the data most
efficiently, do not rely on ``from_file`` and instead perform analysis
directly on the HDF5 data file.

File Header
-----------

The file header can be found in the ``/_header`` HDF5 group. At a
minimum, the header will contain the following HDF5 attributes:

    - ``version``: a string containing the LArPix+HDF5 version
    - ``created``: a Unix timestamp of the file's creation time
    - ``modified``: a Unix timestamp of the file's last-modified time

Versions
--------

The LArPix+HDF5 format is self-describing and versioned. This means as
the format evolves, the files themselves will identify which version
of the format should be used to interpret them. When writing a file
with ``to_file``, the format version can be specified, or by default,
the latest version is used. When reading a file with ``from_file``, by
default, the format version of the actual file is used. If a specific
format version is expected or required, that version can be specified,
and a ``RuntimeError`` will be raised if a different format version is
encountered.

The versions are always in the format ``major.minor`` and are stored as
strings (e.g. ``'1.0'``, ``'1.5'``, ``2.0``).

The minor format will increase if a non-breaking change is made, so that
a script compatible with a lower minor version will also work with files
that have a higher minor version. E.g. a script designed to work with
v1.0 will also work with v1.5. The reverse is not necessarily true: a
script designed to work with v1.5 *may not* work with v1.0 files.

The major format will increase if a breaking change is made. This means
that a script designed to work with v1.5 will *likely not* work with
v2.0 files, and vice versa.

File Data
---------

The file data is saved in HDF5 datasets, and the specific data format
depends on the LArPix+HDF5 version.

Version 2.4 description
^^^^^^^^^^^^^^^^^^^^^^^

For version 2.4, chip configuration objects can be saved to the ``'configs'``
dataset. For compatibility reasons, only 1 type of asic configuration can be
stored per hdf5 file.

The ``configs`` dataset
contains a timestamped entry for each chip config that has been logged

    - Shape: ``(N,)``, ``N >= 0``

    - Attrs: ``asic_version`` (``U25``/unicode string): a global asic version to
      use with this dataset, depending on the asic version a different length
      datatype is used.

    - Datatype: a compound datatype (called "structured type" in
      h5py/numpy).
      Keys/fields:

        - ``timestamp`` (``u8``/unsigned long): a DAQ-system unix timestamp
          associated with when the config was written to the file

        - ``io_group`` (``u1``/unsigned byte): an id associated with the
          high-level io group associated with this network node

        - ``io_channel`` (``u1``/unsigned byte): the id associated with the
          mid-level io channel associated with this network node

        - ``chip_id`` (``u1``/unsigned byte): the id associated with the low-level
          asic

        - ``registers`` (``(239,)u1``: unsigned byte): the value at each of the asic's register addresses

Version 2.3 description
^^^^^^^^^^^^^^^^^^^^^^^

For version 2.3, the ``receipt_timestamp`` (``u4``/unsigned int) field
has been added to the ``packets`` dataset. Additionally, "empty" fields
for data/config write/config read/test packets are now filled according
to the bit content of the packet. E.g. a row representing a config write
packet will still fill the ``dataword`` column as though the packet was
a data packet. Finally, there are some moderate performance improvements.

Version 2.2 description
^^^^^^^^^^^^^^^^^^^^^^^

For version 2.2, two new packet types have been introduced to store
data contained in ``SyncPacket`` and ``TriggerPacket``, with ``type``
being 6 and 7 respectively.

``SyncPacket`` will fill the ``timestamp`` field with the 32-bit
timestamp associated with the sync packet, the ``dataword`` field
with the value of ``clk_source`` (if applicable), ant the
``trigger_type`` field with the sync type (an unsigned byte).

``TriggerPacket`` will fill the ``timestamp`` field with the 32-bit
timestamp associated with the trigger packet and the ``trigger_type``
field with the trigger bits (an unsigned byte).

Version 2.1 description
^^^^^^^^^^^^^^^^^^^^^^^

For version 2.1, there are two dataset: ``packets`` and ``messages``.

The ``packets`` dataset
contains a list of all of the packets sent and received during a
particular time interval.

    - Shape: ``(N,)``, ``N >= 0``

    - Datatype: a compound datatype (called "structured type" in
      h5py/numpy). Not all fields are relevant for each packet. Unused
      fields are set to a default value of 0 or the empty string.
      Keys/fields:

        - ``io_group`` (``u1``/unsigned byte): an id associated with the
          high-level io group associated with this packet

        - ``io_channel`` (``u1``/unsigned byte): the id associated with the
          mid-level io channel associated with this packet

        - ``packet_type`` (``u1``/unsigned byte): the packet type code, which
          can be interpreted according to the map stored in the
          'packets' attribute 'packet_types'

        - ``chip_id`` (``u1``/unsigned byte): the LArPix chip id

        - ``parity`` (``u1``/unsigned byte): the packet parity bit (0 or
          1)

        - ``valid_parity`` (``u1``/unsigned byte): 1 if the packet
          parity is valid (odd), 0 if it is invalid

        - ``downstream_marker`` (``u1``/unsigned byte): a marker to indicate the
          hydra io network direction for this packet

        - ``channel_id`` (``u1``/unsigned byte): the ASIC channel

        - ``timestamp`` (``u8``/unsigned 8-byte long int): the timestamp
          associated with the packet. **Caution**: this field does
          "triple duty" as both the ASIC timestamp in data packets
          (``type`` == 0), as the global timestamp in timestamp
          packets (``type`` == 4), and as the message timestamp in
          message packets (``type`` == 5).

        - ``first_packet`` (``u1``/unsigned byte): indicates if this is the
          packet recieved in a trigger burst (v2.1 or newer only)

        - ``dataword`` (``u1``/unsigned byte): the ADC data word

        - ``trigger_type`` (``u1``/unsigned byte): the trigger type assciated
          with this packet

        - ``local_fifo` (``u1``/unsigned byte): 1 if the channel FIFO is >50%
          full, 3 if the channel FIFO is 100% full

        - ``shared_fifo`` (``u1``/unsigned byte): 1 if the chip FIFO is >50%
          full, 3 if the channel FIFO is 100% full

        - ``register_address`` (``u1``/unsigned byte): the configuration
          register index

        - ``register_data`` (``u1``/unsigned byte): the configuration register
          value

        - ``direction`` (``u1``/unsigned byte): 0 if packet was sent to
          ASICs, 1 if packet was received from ASICs.

        - ``local_fifo_events`` (``u1``/unsigned byte): number of packets in the
          channel FIFO (only valid if FIFO diagnostics are enabled)

        - ``shared_fifo_events`` (``u2``/unsigned byte): number of packets in the
          chip FIFO (only valid if FIFO diagnostics are enabled)

        - ``counter`` (``u4``/unsigned 4-byte int): the message index (only
          valid for message type packets)

        - ``fifo_diagnostics_enabled`` (``u1``/unsigned byte): flag for when
          fifo diagnostics are enabled (1 if enabled, 0 if not)

    - Packet types lookup: the ``packets`` dataset has an attribute
      ``'packet_types'`` which contains the following lookup table for
      packets::

        0: 'data',
        1: 'test',
        2: 'config write',
        3: 'config read',
        4: 'timestamp',
        5: 'message',

The ``messages`` dataset has the full messages referred to by message
packets in the ``packets`` dataset.

    - Shape: ``(N,)``, ``N >= 0``

    - Datatype: a compound datatype with fields:

        - ``message`` (``S64``/64-character string): the message

        - ``timestamp`` (``u8``/unsigned 8-byte long int): the timestamp
          associated with the message

        - ``index`` (``u4``/unsigned 4-byte int): the message index,
          which should be equal to the row index in the ``messages``
          dataset


Version 1.0 description
^^^^^^^^^^^^^^^^^^^^^^^

For version 1.0, there are two dataset: ``packets`` and ``messages``.

The ``packets`` dataset
contains a list of all of the packets sent and received during a
particular time interval.

    - Shape: ``(N,)``, ``N >= 0``

    - Datatype: a compound datatype (called "structured type" in
      h5py/numpy). Not all fields are relevant for each packet. Unused
      fields are set to a default value of 0 or the empty string.
      Keys/fields:

        - ``chip_key`` (``S32``/32-character string): the chip key
          identifying the ASIC associated with this packet

        - ``type`` (``u1``/unsigned byte): the packet type code, which
          can be interpreted according to the map stored in the
          raw_packet attribute 'packet_types'

        - ``chipid`` (``u1``/unsigned byte): the LArPix chipid

        - ``parity`` (``u1``/unsigned byte): the packet parity bit (0 or
          1)

        - ``valid_parity`` (``u1``/unsigned byte): 1 if the packet
          parity is valid (odd), 0 if it is invalid

        - ``channel`` (``u1``/unsigned byte): the ASIC channel

        - ``timestamp`` (``u8``/unsigned 8-byte long int): the timestamp
          associated with the packet. **Caution**: this field does
          "triple duty" as both the ASIC timestamp in data packets
          (``type`` == 0), as the global timestamp in timestamp
          packets (``type`` == 4), and as the message timestamp in
          message packets (``type`` == 5).

        - ``adc_counts`` (``u1``/unsigned byte): the ADC data word

        - ``fifo_half`` (``u1``/unsigned byte): 1 if the FIFO half full
          flag is present, 0 otherwise.

        - ``fifo_full`` (``u1``/unsigned byte): 1 if the FIFO full flag
          is present, 0 otherwise.

        - ``register`` (``u1``/unsigned byte): the configuration
          register index

        - ``value`` (``u1``/unsigned byte): the configuration register
          value

        - ``counter`` (``u4``/unsigned 4-byte int): the test counter
          value, or the message index. **Caution**: this field does
          "double duty" as the counter for test packets (``type`` == 1)
          and as the message index for message packets (``type`` == 5).

        - ``direction`` (``u1``/unsigned byte): 0 if packet was sent to
          ASICs, 1 if packet was received from ASICs.

    - Packet types lookup: the ``packets`` dataset has an attribute
      ``'packet_types'`` which contains the following lookup table for
      packets::

        0: 'data',
        1: 'test',
        2: 'config write',
        3: 'config read',
        4: 'timestamp',
        5: 'message',

The ``messages`` dataset has the full messages referred to by message
packets in the ``packets`` dataset.

    - Shape: ``(N,)``, ``N >= 0``

    - Datatype: a compound datatype with fields:

        - ``message`` (``S64``/64-character string): the message

        - ``timestamp`` (``u8``/unsigned 8-byte long int): the timestamp
          associated with the message

        - ``index`` (``u4``/unsigned 4-byte int): the message index,
          which should be equal to the row index in the ``messages``
          dataset

Examples
--------

Plot a histogram of ADC counts (selecting packet type to be data packets
only)

>>> import matplotlib.pyplot as plt
>>> import h5py
>>> f = h5py.File('output.h5', 'r')
>>> packets = f['packets']
>>> plt.hist(packets['adc_counts'][packets['type'] == 0])
>>> plt.show()

Load the first 10 packets in a file into Packet objects and print any
MessagePacket packets to the console

>>> from larpix.format.hdf5format import from_file
>>> from larpix.larpix import MessagePacket
>>> result = from_file('output.h5', end=10)
>>> for packet in result['packets']:
...     if isinstance(packet, MessagePacket):
...         print(packet)



'''
import time
import os
import multiprocessing

import h5py
import numpy as np
import struct

from larpix.larpix import Packet_v1, Packet_v2, TimestampPacket, MessagePacket, SyncPacket, TriggerPacket, Chip, Configuration_Lightpix_v1, Key
from larpix.logger import Logger
from .. import bitarrayhelper as bah
_max_config_registers = Configuration_Lightpix_v1.num_registers

#: The most recent / up-to-date LArPix+HDF5 format version
latest_version = '2.4'

#: The dtype specification used in the HDF5 files.
#:
#: Structure: ``{version: {dset_name: [structured dtype fields]}}``
dtypes = dict()
dtypes['0.0'] = {
            'raw_packet': [
                ('chip_key','S32'),
                ('type','u1'),
                ('chipid','u1'),
                ('parity','u1'),
                ('valid_parity','u1'),
                ('counter','u4'),
                ('channel','u1'),
                ('timestamp','u8'),
                ('adc_counts','u1'),
                ('fifo_half','u1'),
                ('fifo_full','u1'),
                ('register','u1'),
                ('value','u1'),
                ]
            }
dtypes['1.0'] = { # compatible with v1 packets only
            'packets': [
                ('chip_key','S32'),
                ('type','u1'),
                ('chipid','u1'),
                ('parity','u1'),
                ('valid_parity','u1'),
                ('channel','u1'),
                ('timestamp','u8'),
                ('adc_counts','u1'),
                ('fifo_half','u1'),
                ('fifo_full','u1'),
                ('register','u1'),
                ('value','u1'),
                ('counter','u4'),
                ('direction', 'u1'),
                ],
            'messages': [
                ('message', 'S64'),
                ('timestamp', 'u8'),
                ('index', 'u4'),
                ]
            }
dtypes['2.0'] = { # compatible with v2 packets and timestamp packets only
            'packets': [
                ('io_group','u1'),
                ('io_channel','u1'),
                ('chip_id','u1'),
                ('packet_type','u1'),
                ('downstream_marker','u1'),
                ('parity','u1'),
                ('valid_parity','u1'),
                ('channel_id','u1'),
                ('timestamp','u8'),
                ('dataword','u1'),
                ('trigger_type','u1'),
                ('local_fifo','u1'),
                ('shared_fifo','u1'),
                ('register_address','u1'),
                ('register_data','u1'),
                ('direction', 'u1'),
                ('local_fifo_events','u1'),
                ('shared_fifo_events','u2'),
                ('counter','u4'),
                ('fifo_diagnostics_enabled','u1'),
                ],
            'messages': [
                ('message', 'S64'),
                ('timestamp', 'u8'),
                ('index', 'u4'),
                ]
            }
dtypes['2.1'] = dtypes['2.0'].copy() # compatible with v2 packets and timestamp packets only
dtypes['2.1']['packets'].append(('first_packet','u1'))
dtypes['2.2'] = dtypes['2.1'].copy() # compatible with v2 packets, timestamp packets, sync packets, and trigger packets only
dtypes['2.3'] = dtypes['2.2'].copy() # compatible with v2 packets, timestamp packets, sync packets, and trigger packets only
dtypes['2.3']['packets'].append(('receipt_timestamp','u4'))
dtypes['2.4'] = dtypes['2.3'].copy() # compatible with v2 packets, timestamp packets, sync packets, and trigger packets only
dtypes['2.4']['configs'] = [
    ('timestamp','u8'),
    ('io_group','u1'),
    ('io_channel','u1'),
    ('chip_id','u1'),
    ('registers','({},)u1'.format(_max_config_registers))
]

#: A map between attribute name and "column index" in the structured
#: dtypes.
#:
#: Structure: ``{version: {dset_name: {field_name: index}}}``
dtype_property_index_lookup = dict()
dtype_property_index_lookup['0.0'] = {
            'raw_packet': {
                'chip_key': 0,
                'type': 1,
                'chipid': 2,
                'parity': 3,
                'valid_parity': 4,
                'counter': 5,
                'channel': 6,
                'timestamp': 7,
                'adc_counts': 8,
                'fifo_half': 9,
                'fifo_full': 10,
                'register': 11,
                'value': 12,
                }
            }
dtype_property_index_lookup['1.0'] = {
            'packets': {
                'chip_key': 0,
                'type': 1,
                'chipid': 2,
                'parity': 3,
                'valid_parity': 4,
                'channel': 5,
                'timestamp': 6,
                'adc_counts': 7,
                'fifo_half': 8,
                'fifo_full': 9,
                'register': 10,
                'value': 11,
                'counter': 12,
                'direction': 13,
                },
            'messages': {
                'message': 0,
                'timestamp': 1,
                'index': 2,
                }
            }
dtype_property_index_lookup['2.0'] = {
            'packets': {
                'io_group': 0,
                'io_channel': 1,
                'chip_id': 2,
                'packet_type': 3,
                'downstream_marker': 4,
                'parity': 5,
                'valid_parity': 6,
                'channel_id': 7,
                'timestamp': 8,
                'dataword': 9,
                'trigger_type': 10,
                'local_fifo': 11,
                'shared_fifo': 12,
                'register_address': 13,
                'register_data': 14,
                'direction': 15,
                'local_fifo_events': 16,
                'shared_fifo_events': 17,
                'counter': 18,
                'fifo_diagnostics_enabled': 19,
                },
            'messages': {
                'message': 0,
                'timestamp': 1,
                'index': 2,
                }
            }
dtype_property_index_lookup['2.1'] = dtype_property_index_lookup['2.0'].copy()
dtype_property_index_lookup['2.1']['packets']['first_packet'] = 20
dtype_property_index_lookup['2.2'] = dtype_property_index_lookup['2.1'].copy()
dtype_property_index_lookup['2.3'] = dtype_property_index_lookup['2.2'].copy()
dtype_property_index_lookup['2.3']['packets']['receipt_timestamp'] = 21
dtype_property_index_lookup['2.4'] = dtype_property_index_lookup['2.3'].copy()
dtype_property_index_lookup['2.4']['configs'] = {
    'timestamp': 0,
    'io_group': 1,
    'io_channel': 2,
    'chip_id': 3,
    'registers': 4
}

def _format_raw_packet_v0_0(pkt, version='0.0', dset='raw_packet', *args, **kwargs):
    dict_rep = pkt.export()
    encoded_packet = [
        dict_rep.get(key, b'') if val_type[0] == 'S'  # string
        else dict_rep.get(key, 0) for key, val_type in
        dtypes[version][dset]]
    return encoded_packet

def _parse_raw_packet_v0_0(row, message_dset, *args, **kwargs):
    if row['type'] == 4:
        return TimestampPacket(row['timestamp'])
    if row['type'] < 4:
        p = Packet_v1()
        p.chip_key = row['chip_key']
        p.packet_type = row['type']
        p.chipid = row['chipid']
        p.parity_bit_value = row['parity']
        if p.packet_type == Packet_v1.DATA_PACKET:
            p.channel = row['channel']
            p.timestamp = row['timestamp']
            p.dataword = row['adc_counts']
            p.fifo_half_flag = row['fifo_half']
            p.fifo_full_flag = row['fifo_full']
        elif p.packet_type == Packet_v1.TEST_PACKET:
            p.counter = row['counter']
        elif (p.packet_type == Packet_v1.CONFIG_WRITE_PACKET
              or p.packet_type == Packet_v1.CONFIG_READ_PACKET):
            p.register_address = row['register']
            p.register_data = row['value']
        return p
    return None

def _format_packets_packet_v1_0(pkt, version='1.0', dset='packets', *args, **kwargs):
    encoded_packet = _format_raw_packet_v0_0(pkt, *args, version=version, dset=dset, **kwargs)
    if hasattr(pkt, 'direction'):
        encoded_packet[dtype_property_index_lookup[version][dset]['direction']] = {
            Logger.WRITE: 0,
            Logger.READ: 1}[pkt.direction]
    return encoded_packet

def _format_messages_message_packet_v1_0(pkt, counter=0, *args, **kwargs):
    return (pkt.message, pkt.timestamp, counter)

def _parse_packets_v1_0(row, message_dset, *args, **kwargs):
    if row['type'] == 4:
        return TimestampPacket(row['timestamp'])
    if row['type'] == 5:
        index = row['counter']
        message_row = message_dset[index]
        message = message_row['message'].decode()
        timestamp = row['timestamp']
        return MessagePacket(message, timestamp)
    if row['type'] < 4:
        p = Packet_v1()
        p.chip_key = row['chip_key']
        p.packet_type = row['type']
        p.chipid = row['chipid']
        p.parity_bit_value = row['parity']
        if p.packet_type == Packet_v1.DATA_PACKET:
            p.channel = row['channel']
            p.timestamp = row['timestamp']
            p.dataword = row['adc_counts']
            p.fifo_half_flag = row['fifo_half']
            p.fifo_full_flag = row['fifo_full']
        elif p.packet_type == Packet_v1.TEST_PACKET:
            p.counter = row['counter']
        elif (p.packet_type == Packet_v1.CONFIG_WRITE_PACKET
              or p.packet_type == Packet_v1.CONFIG_READ_PACKET):
            p.register_address = row['register']
            p.register_data = row['value']
        p.direction = row['direction']
        return p
    return None

def _format_packets_packet_v2_0(pkt, version='2.0', dset='packets', *args, **kwargs):
    encoded_packet = _format_packets_packet_v1_0(pkt, version=version, dset=dset)
    if encoded_packet is not None:
        encoded_packet[dtype_property_index_lookup[version][dset]['packet_type']] = pkt.packet_type
        if isinstance(pkt, Packet_v2) and pkt.fifo_diagnostics_enabled:
            encoded_packet[dtype_property_index_lookup[version][dset]['fifo_diagnostics_enabled']] = 1
    return encoded_packet

def _parse_packets_v2_0(row, message_dset, *args, **kwargs):
    if row['packet_type'] == 4:
        return TimestampPacket(row['timestamp'])
    if row['packet_type'] == 5:
        index = row['counter']
        message_row = message_dset[index]
        message = message_row['message'].decode()
        timestamp = row['timestamp']
        return MessagePacket(message, timestamp)
    if row['packet_type'] < 4:
        p = Packet_v2()
        p.io_group = row['io_group']
        p.io_channel = row['io_channel']
        p.chip_id = row['chip_id']
        p.packet_type = row['packet_type']
        p.downstream_marker = row['downstream_marker']
        p.parity = row['parity']
        p.valid_parity = row['valid_parity']
        p.direction = row['direction']
        if p.packet_type == Packet_v2.DATA_PACKET:
            p.channel_id = row['channel_id']
            p.timestamp = row['timestamp']
            p.dataword = row['dataword']
            p.trigger_type = row['trigger_type']
            p.local_fifo = row['local_fifo']
            p.shared_fifo = row['shared_fifo']
            if row['fifo_diagnostics_enabled'] != 0:
                p.fifo_diagnostics_enabled = True
                p.local_fifo = row['local_fifo_events']
                p.shared_fifo = row['shared_fifo_events']
                p.timestamp = row['timestamp']
        elif p.packet_type in (Packet_v2.CONFIG_READ_PACKET, Packet_v2.CONFIG_WRITE_PACKET):
            p.register_address = row['register_address']
            p.register_data = row['register_data']
        return p
    return None

def _format_packets_packet_v2_1(pkt, version='2.1', dset='packets', *args, **kwargs):
    return _format_packets_packet_v2_0(pkt, *args, version=version, dset=dset, **kwargs)

def _parse_packets_v2_1(row, message_dset, *args, **kwargs):
    p = _parse_packets_v2_0(row, message_dset, *args, **kwargs)
    if isinstance(p, Packet_v2):
        p.first_packet = row['first_packet']
    return p

_uint8_struct = struct.Struct("<B")
def _format_packets_packet_v2_2(pkt, version='2.2', dset='packets', *args, **kwargs):
    encoded_packet = _format_packets_packet_v2_0(pkt, *args, version=version, dset=dset, **kwargs)
    if isinstance(pkt, SyncPacket):
        encoded_packet[dtype_property_index_lookup[version]['packets']['trigger_type']] = _uint8_struct.unpack(pkt.sync_type)[0]
        encoded_packet[dtype_property_index_lookup[version]['packets']['dataword']] = pkt.clk_source
    elif isinstance(pkt, TriggerPacket):
        encoded_packet[dtype_property_index_lookup[version]['packets']['trigger_type']] = _uint8_struct.unpack(pkt.trigger_type)[0]
    return encoded_packet

def _parse_packets_v2_2(row, message_dset, *args, **kwargs):
    p = _parse_packets_v2_1(row, message_dset, *args, **kwargs)
    if p is None:
        if row['packet_type'] == 6:
            return SyncPacket(
                io_group = row['io_group'],
                sync_type = _uint8_struct.pack(row['trigger_type']),
                clk_source = row['dataword'],
                timestamp = row['timestamp']
            )
        if row['packet_type'] == 7:
            return TriggerPacket(
                io_group = row['io_group'],
                trigger_type = _uint8_struct.pack(row['trigger_type']),
                timestamp = row['timestamp']
            )
    return p

def _format_packets_packet_v2_3(pkt, version='2.3', dset='packets', *args, **kwargs):
    encoded_packet = [0]*len(dtypes[version][dset])
    i = 0
    for value_name, value_type in dtypes[version][dset]:
        encoded_packet[i] = getattr(pkt, value_name, None)
        if encoded_packet[i] is None:
            if value_name == 'valid_parity' and hasattr(pkt, 'has_valid_parity'):
                encoded_packet[i] = pkt.has_valid_parity()
            elif value_type[0] == 'S': # string default
                encoded_packet[i] = ''
            else:
                encoded_packet[i] = 0
        i += 1
    if pkt.packet_type == 6: # sync packets
        encoded_packet[dtype_property_index_lookup[version]['packets']['trigger_type']] = _uint8_struct.unpack(pkt.sync_type)[0]
        encoded_packet[dtype_property_index_lookup[version]['packets']['dataword']] = pkt.clk_source
    elif pkt.packet_type == 7: # trigger packets
        encoded_packet[dtype_property_index_lookup[version]['packets']['trigger_type']] = _uint8_struct.unpack(pkt.trigger_type)[0]
    return encoded_packet

def _parse_packets_v2_3(row, message_dset, *args, **kwargs):
    p = _parse_packets_v2_2(row, message_dset, *args, **kwargs)
    if isinstance(p, Packet_v2):
        p.receipt_timestamp = row['receipt_timestamp']
    return p

def _format_configs_chip_v2_4(chip, version='2.4', dset='configs', timestamp=0, *args, **kwargs):
    row = np.zeros((1,),dtype=dtypes[version][dset])
    row['timestamp'] = timestamp
    row['io_group'] = chip.io_group
    row['io_channel'] = chip.io_channel
    row['chip_id'] = chip.chip_id
    endian='big' if chip.asic_version == 1 else 'little'
    for i,bits in enumerate(chip.config.all_data()):
        row['registers'][0,i] = bah.touint(bits, endian=endian)
    return row

def _parse_configs_v2_4(row, asic_version, *args, **kwargs):
    key = Key(row['io_group'],row['io_channel'],row['chip_id'])
    if asic_version in ('1','2'):
        c = Chip(key,version=int(asic_version))
    else:
        c = Chip(key,version=asic_version)
    d = dict()
    for i in range(c.config.num_registers):
        d[i] = row['registers'][i]
    endian = 'big' if asic_version == '1' else 'little'
    c.config.from_dict_registers(d, endian=endian)
    return c

# A map between packet class and the formatting method used to convert to structured
# dtypes.
#
# Structure: ``{version: {dset_name: {larpix_packet_class: format_method}}}``
_format_method_lookup = {
    '0.0': {
        'raw_packet': {
            Packet_v1: _format_raw_packet_v0_0,
            TimestampPacket: _format_raw_packet_v0_0
        }
    },
    '1.0': {
        'packets': {
            Packet_v1: _format_packets_packet_v1_0,
            TimestampPacket: _format_packets_packet_v1_0,
            MessagePacket: _format_packets_packet_v1_0
        },
        'messages': {
            MessagePacket: _format_messages_message_packet_v1_0
        }
    },
    '2.0': {
        'packets': {
            Packet_v2: _format_packets_packet_v2_0,
            TimestampPacket: _format_packets_packet_v2_0,
            MessagePacket: _format_packets_packet_v2_0
        },
        'messages': {
            MessagePacket: _format_messages_message_packet_v1_0
        }
    },
    '2.1': {
        'packets': {
            Packet_v2: _format_packets_packet_v2_1,
            TimestampPacket: _format_packets_packet_v2_1,
            MessagePacket: _format_packets_packet_v2_1
        },
        'messages': {
            MessagePacket: _format_messages_message_packet_v1_0
        }
    },
    '2.2': {
        'packets': {
            Packet_v2: _format_packets_packet_v2_1,
            TimestampPacket: _format_packets_packet_v2_1,
            MessagePacket: _format_packets_packet_v2_1,
            SyncPacket: _format_packets_packet_v2_2,
            TriggerPacket: _format_packets_packet_v2_2
        },
        'messages': {
            MessagePacket: _format_messages_message_packet_v1_0
        },
    },
    '2.3': {
        'packets': {
            Packet_v2: _format_packets_packet_v2_3,
            TimestampPacket: _format_packets_packet_v2_3,
            MessagePacket: _format_packets_packet_v2_3,
            SyncPacket: _format_packets_packet_v2_3,
            TriggerPacket: _format_packets_packet_v2_3
        },
        'messages': {
            MessagePacket: _format_messages_message_packet_v1_0
        }
    },
    '2.4': {
        'packets': {
            Packet_v2: _format_packets_packet_v2_3,
            TimestampPacket: _format_packets_packet_v2_3,
            MessagePacket: _format_packets_packet_v2_3,
            SyncPacket: _format_packets_packet_v2_3,
            TriggerPacket: _format_packets_packet_v2_3
        },
        'messages': {
            MessagePacket: _format_messages_message_packet_v1_0
        },
        'configs': {
            Chip: _format_configs_chip_v2_4
        }
    },
}

# A map between dset the parsing method used to convert from structured
# dtypes.
#
# Structure: ``{version: {dset_name: {larpix_packet_class: parse_method}}}``
_parse_method_lookup = {
    '0.0': {
        'raw_packet': _parse_raw_packet_v0_0
    },
    '1.0': {
        'packets': _parse_packets_v1_0
    },
    '2.0': {
        'packets': _parse_packets_v2_0
    },
    '2.1': {
        'packets': _parse_packets_v2_1
    },
    '2.2': {
        'packets': _parse_packets_v2_2
    },
    '2.3': {
        'packets': _parse_packets_v2_3
    },
    '2.4': {
        'packets': _parse_packets_v2_3,
        'configs': _parse_configs_v2_4
    }
}

def _encode_packet(packet, version, packet_dset_name):
    '''
    Worker function to parse a packet into a tuple to be used as a numpy structured type

    '''
    if packet.__class__ in _format_method_lookup[version].get(packet_dset_name, tuple()):
        encoded_packet = _format_method_lookup[version][packet_dset_name][packet.__class__](packet)
        for idx in range(len(encoded_packet)):
            if encoded_packet[idx] is None:
                encoded_packet[idx] = 0
        return(tuple(encoded_packet))
    return False

def to_file(filename, packet_list=None, chip_list=None, mode='a', version=None, workers=None):
    '''
    Save the given packets to the given file.

    This method can be used to update an existing file.

    :param filename: the name of the file to save to
    :param packet_list: any iterable of objects of type ``Packet``,
        ``TimestampPacket``, ``SyncPacket``, or ``TriggerPacket``.
    :param chip_list: any iterable of objects of type ``Chip``.
    :param mode: optional, the "file mode" to open the data file
        (default: ``'a'``)
    :param version: optional, the LArPix+HDF5 format version to use. If
        writing a new file and version is unspecified or ``None``,
        the latest version will be used. If writing an existing file
        and version is unspecified or ``None``, the existing file's
        version will be used. If writing an existing file and version
        is specified and does not exactly match the existing file's
        version, a ``RuntimeError`` will be raised. (default: ``None``)

    '''
    if packet_list is None: packet_list = []
    if chip_list is None: chip_list = []
    if workers is None:
      workers = max(min(os.cpu_count(), int(len(packet_list)//10000)),1)

    with h5py.File(filename, mode) as f:
        # Create header
        if '_header' not in f.keys():
            header = f.create_group('_header')
            if version is None:
                version = latest_version
            header.attrs['version'] = version
            header.attrs['created'] = time.time()
        else:
            header = f['_header']
            file_version = header.attrs['version']
            if version is None:
                version = file_version
            elif header.attrs['version'] != version:
                raise RuntimeError('Incompatible versions: existing: %s, '
                    'specified: %s' % (file_version, version))
        header.attrs['modified'] = time.time()

        # Create datasets
        if version == '0.0':
            packet_dset_name = 'raw_packet'
        else:
            packet_dset_name = 'packets'
            direction_index = (
                    dtype_property_index_lookup[version]['packets']
                    ['direction'])
            if version[0] == '2':
                packet_type_index = (
                        dtype_property_index_lookup[version]['packets']
                        ['packet_type'])
                fifo_diagnostics_enabled_index = (
                        dtype_property_index_lookup[version]['packets']
                        ['fifo_diagnostics_enabled'])
                trigger_type_index = (
                        dtype_property_index_lookup[version]['packets']
                        ['trigger_type'])
                dataword_index = (
                        dtype_property_index_lookup[version]['packets']
                        ['dataword'])
        packet_dtype = dtypes[version][packet_dset_name]
        if packet_dset_name not in f.keys():
            packet_dset = f.create_dataset(packet_dset_name, shape=(len(packet_list),),
                    maxshape=(None,), dtype=packet_dtype)
            if version[0] == '1' or version[0] == '2':
                if version[-1] == '2' and version[0] == '2':
                    packet_dset.attrs['packet_types'] = '''
0: 'data',
1: 'test',
2: 'config write',
3: 'config read',
4: 'timestamp',
5: 'message',
6: 'sync',
7: 'trigger,
'''
                else:
                    packet_dset.attrs['packet_types'] = '''
0: 'data',
1: 'test',
2: 'config write',
3: 'config read',
4: 'timestamp',
5: 'message',
'''
            start_index = 0
        else:
            packet_dset = f[packet_dset_name]
            start_index = packet_dset.shape[0]
            packet_dset.resize(start_index + len(packet_list), axis=0)

        if version != '0.0':
            message_dset_name = 'messages'
            message_dtype = dtypes[version][message_dset_name]
            if message_dset_name not in f.keys():
                message_dset = f.create_dataset(message_dset_name,
                        shape=(0,), maxshape=(None,),
                        dtype=message_dtype)
                message_start_index = 0
            else:
                message_dset = f[message_dset_name]
                message_start_index = message_dset.shape[0]

        if version >= '2.4':
            configs_dset_name = 'configs'
            configs_dtype = dtypes[version][configs_dset_name]
            if configs_dset_name not in f.keys():
                configs_dset = f.create_dataset(configs_dset_name,
                    shape=(0,), maxshape=(None,),
                    dtype=configs_dtype)
                configs_start_index = 0
            else:
                configs_dset = f[configs_dset_name]
                configs_start_index = configs_dset.shape[0]
            if chip_list:
                configs_dset.attrs['asic_version'] = str(chip_list[-1].asic_version)

        # Fill dataset
        encoded_packets = []
        messages = []
        configs = []

        if workers > 1:
            packet_args = zip(packet_list, [version]*len(packet_list), [packet_dset_name]*len(packet_list))
            with multiprocessing.Pool(workers) as p:
                encoded_packets = list(filter(bool, p.starmap(_encode_packet, packet_args)))
        else:
            encoded_packets = list(filter(bool, [_encode_packet(packet, version, packet_dset_name) for packet in packet_list]))

        for i, packet in enumerate(packet_list):
            if version != '0.0' and packet.__class__ in _format_method_lookup[version].get(message_dset_name, tuple()):
                encoded_message = _format_method_lookup[version][message_dset_name][packet.__class__](packet, counter=message_start_index + len(messages))
                messages.append(encoded_message)

        for i,chip in enumerate(chip_list):
            if version >= '2.4':
                encoded_config = _format_method_lookup[version][configs_dset_name][chip.__class__](chip, counter=configs_start_index + len(configs), timestamp=header.attrs['modified'])
                configs.append(encoded_config)

        if encoded_packets:
            packet_dset[start_index:] = encoded_packets
        if version != '0.0' and messages:
            message_dset.resize(message_start_index + len(messages), axis=0)
            message_dset[message_start_index:] = messages
        if version >= '2.4' and configs:
            configs_dset.resize(configs_start_index + len(configs), axis=0)
            configs_dset[configs_start_index:] = np.concatenate(configs)

def from_file(filename, version=None, start=None, end=None, load_configs=None):
    '''
    Read the data from the given file into LArPix Packet objects.

    :param filename: the name of the file to read
    :param version: the format version. Specify this parameter to
        enforce a version check. When a specific version such as
        ``'1.5'`` is specified, a ``RuntimeError`` will be raised if the
        stored format version number is not an exact match. If a version
        is prefixed with ``'~'`` such as ``'~1.5'``, a ``RuntimeError``
        will be raised if the stored format version is *incompatible*
        with the specified version. Compatible versions are those with
        the same major version and at least the same minor version. E.g.
        for ``'~1.5'``, versions between v1.5 and v2.0 are compatible.
        If unspecified or ``None``, will use the stored format version.
    :param start: the index of the first row to read
    :param end: the index after the last row to read (same semantics as
        Python ``range``)
    :param load_configs: a flag to indicate if configs should be fetched from file, a
        value of ``True`` will load all configs and a value of type ``slice``
        will load the specified subset.
    :returns packet_dict: a dict with keys ``'packets'`` containing a
        list of packet objects; ``'configs'`` containing a list of chip objects;
        and ``'created'``, ``'modified'``, and
        ``'version'``, containing the file metadata.

    '''
    with h5py.File(filename, 'r') as f:
        file_version = f['_header'].attrs['version']
        if version is None:
            version = file_version
        elif version[0] == '~':
            file_major, _, file_minor = file_version.split('.')
            version_major, _, version_minor = version.split('.')
            version_major = version_major[1:]
            if (file_major != version_major
                    or file_minor < version_minor):
                raise RuntimeError('Incompatible versions: existing: %s, '
                    'specified: %s' % (file_version, version))
            else:
                version = file_version
        elif version == file_version:
            pass
        else:
            raise RuntimeError('Incompatible versions: existing: %s, '
                'specified: %s' % (file_version, version))

        if version not in dtypes:
            raise RuntimeError('Unknown version: %s' % version)

        if version == '0.0':
            dset_name = 'raw_packet'
            message_dset = None
            configs_dset = None
        else:
            dset_name = 'packets'
            message_dset_name = 'messages'
            message_props = (
                    dtype_property_index_lookup[version][message_dset_name])
            message_dset = f[message_dset_name]

        props = dtype_property_index_lookup[version][dset_name]
        packets = []
        if start is None and end is None:
            dset_iter = f[dset_name]
        else:
            dset_iter = f[dset_name][start:end]
        for row in dset_iter:
            pkt = _parse_method_lookup[version][dset_name](row, message_dset)
            if pkt is not None:
                packets.append(pkt)

        configs = []
        if version >= '2.4':
            dset_name ='configs'
            if load_configs:
                if isinstance(load_configs,bool):
                    dset_iter = f[dset_name]
                else:
                    dset_iter = f[dset_name][load_configs]
                asic_version = f[dset_name].attrs['asic_version']
                for row in dset_iter:
                    chip = _parse_method_lookup[version][dset_name](row, asic_version=asic_version)
                    if chip is not None:
                        configs.append(chip)
        return {
                'packets': packets,
                'configs': configs,
                'created': f['_header'].attrs['created'],
                'modified': f['_header'].attrs['modified'],
                'version': f['_header'].attrs['version'],
                }

