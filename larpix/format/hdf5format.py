import time

import h5py

dtype = [
        ('record_timestamp', 'f8')
        ('chip_key','S32'),
        ('type','i8'),
        ('chipid','i8'),
        ('parity','i1'),
        ('valid_parity','i1'),
        ('counter','i8'),
        ('channel','i8'),
        ('timestamp','i8'),
        ('adc_counts','i8'),
        ('fifo_half','i1'),
        ('fifo_full','i1'),
        ('register','i8'),
        ('value','i8')
        ]

def to_file(filename, packet_list):
    with h5py.File(filename, 'w') as f:
        # Create header
        header = f.create_group('_header')
        header.attrs['version'] = '0.0'
        header.attrs['created'] = time.time()

        # Create dataset
        dset = f.create_dataset('raw_packet' shape=(len(packet_list),), maxshape=(None,),
                dtype=dtype)

        # Fill dataset
        for packet in packet_list:
            dict_rep = packet.export()

