import time

import h5py
import numpy as np

from larpix.larpix import Packet, TimestampPacket

# {version: {dset_name: [structured dtype fields]}}
dtypes = {
        '0.0': {
            'raw_packet': [
                ('chip_key','S32'),
                ('type','S12'),
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
                ('value','u1')
                ]
            }
        }

def to_file(filename, packet_list, mode='a', version='0.0'):
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
                (dict_rep.get(key, 0) for key, _ in dtype)))
        dset[start_index:] = encoded_packets

def from_file(filename):
    with h5py.File(filename, 'r') as f:
        if f['_header'].attrs['version'] != '0.0':
            raise RuntimeError('Invalid version (should be 0.0): %s' %
                    f['_header'].attrs['version'])
        packets = []
        for row in f['raw_packet']:
            if row[1] == b'timestamp':
                packets.append(TimestampPacket(row[7]))
                continue
            p = Packet()
            p.type = {
                    b'data': Packet.DATA_PACKET,
                    b'test': Packet.TEST_PACKET,
                    b'config write': Packet.CONFIG_WRITE_PACKET,
                    b'config read': Packet.CONFIG_READ_PACKET,
                    }[row[1]]
            p.chip_key = row[0]
            p.chipid = row[2]
            p.parity = row[3]
            if p.type == Packet.DATA_PACKET:
                p.channel = row[6]
                p.timestamp = row[7]
                p.dataword = row[8]
                p.fifo_half_flag = row[9]
                p.fifo_full_flag = row[10]
            elif p.type == Packet.TEST_PACKET:
                p.counter = row[5]
            elif (p.type == Packet.CONFIG_WRITE_PACKET
                    or p.type == Packet.CONFIG_READ_PACKET):
                p.register_address = row[11]
                p.register_data = row[12]
            packets.append(p)
        return {
                'packets': packets,
                'created': f['_header'].attrs['created'],
                'version': f['_header'].attrs['version'],
                }
