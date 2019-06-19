'''
This module gives access to the LArPix+HDF5 file format.

File format description
=======================

All LArPix+HDF5 files use the HDF5 format so that they
can be read and written using any language that has an HDF5 binding.

LArPix+HDF5 files are self-describing in that they contain a format
version which identifies the structure of the file.

File Header
-----------

The file header can be found in the ``/_header`` HDF5 group. At a
minimum, the header will contain the following HDF5 attributes:

    - ``version``: a string containing the LArPix+HDF5 version
    - ``created``: a Unix timestamp of the file's creation time
    - ``modified``: a Unix timestamp of the files last-modified time

File Data
---------

The file data is saved in HDF5 datasets, and the specific data format
depends on the LArPix+HDF5 version.

For version 0.0, there is only one dataset: ``raw_packet``. This dataset
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
          associated with the packet

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
          value

        - ``direction`` (``u1``/unsigned byte): 0 if packet was sent to
          ASICs, 1 if packet was received from ASICs.

'''
import time

import h5py
import numpy as np

from larpix.larpix import Packet, TimestampPacket, DirectionPacket

# {version: {dset_name: [structured dtype fields]}}
dtypes = {
        '0.0': {
            'raw_packet': [
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
                ]
            }
        }

def to_file(filename, packet_list, mode='a', version='0.0'):
    '''
    Save the given packets to the given file.

    This method can be used to update an existing file.

    :param filename: the name of the file to save to
    :param packet_list: any iterable of objects of type ``Packet``,
        ``TimestampPacket``, or ``DirectionPacket``.
    :param mode: optional, the "file mode" to open the data file
        (default: ``'a'``)
    :param version: optional, the LArPix+HDF5 format version to use (for
        backwards compatibility pick an earlier version) (default: '0.0')

    '''
    with h5py.File(filename, mode) as f:
        # Create header
        if '_header' not in f.keys():
            header = f.create_group('_header')
            header.attrs['version'] = version
            header.attrs['created'] = time.time()
        else:
            header = f['_header']
        header.attrs['modified'] = time.time()

        # Create dataset
        dtype = dtypes[version]['raw_packet']
        if 'raw_packet' not in f.keys():
            dset = f.create_dataset('raw_packet', shape=(len(packet_list),),
                    maxshape=(None,), dtype=dtype)
            dset.attrs['packet_types'] = '''
0: 'data',
1: 'test',
2: 'config write',
3: 'config read',
4: 'timestamp',
5: 'direction',
'''
            start_index = 0
        else:
            dset = f['raw_packet']
            start_index = dset.shape[0]
            dset.resize(start_index + len(packet_list), axis=0)

        # Fill dataset
        encoded_packets = []
        for packet in packet_list:
            dict_rep = packet.export()
            encoded_packets.append(tuple(
                (dict_rep.get(key, b'') if val_type[0] == 'S'  # string
                    else dict_rep.get(key, 0) for key, val_type in dtype)))
        dset[start_index:] = encoded_packets

def from_file(filename):
    '''
    Read the data from the given file into LArPix Packet objects.

    :param filename: the name of the file to read
    :returns packet_dict: a dict with keys ``'packets'`` containing a
        list of packet objects; and ``'created'``, ``'modified'``, and
        ``'version'``, containing the file metadata.

    '''
    with h5py.File(filename, 'r') as f:
        if f['_header'].attrs['version'] != '0.0':
            raise RuntimeError('Invalid version (should be 0.0): %s' %
                    f['_header'].attrs['version'])
        packets = []
        for row in f['raw_packet']:
            if row[1] == 4:
                packets.append(TimestampPacket(row[6]))
                continue
            if row[1] == 5:
                packets.append(DirectionPacket(row[13]))
                continue
            p = Packet()
            p.chip_key = row[0]
            p.packet_type = row[1]
            p.chipid = row[2]
            p.parity_bit_value = row[3]
            if p.packet_type == Packet.DATA_PACKET:
                p.channel = row[5]
                p.timestamp = row[6]
                p.dataword = row[7]
                p.fifo_half_flag = row[8]
                p.fifo_full_flag = row[9]
            elif p.packet_type == Packet.TEST_PACKET:
                p.counter = row[12]
            elif (p.packet_type == Packet.CONFIG_WRITE_PACKET
                    or p.packet_type == Packet.CONFIG_READ_PACKET):
                p.register_address = row[10]
                p.register_data = row[11]
            packets.append(p)
        return {
                'packets': packets,
                'created': f['_header'].attrs['created'],
                'modified': f['_header'].attrs['modified'],
                'version': f['_header'].attrs['version'],
                }
