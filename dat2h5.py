'''
A script to convert a .dat data file into a simple h5 file with the
following columns:

    channel id | chip id | pixel id | pixel x | pixel y | raw ADC | raw
    timestamp | 6-bit ADC | full timestamp

'''

import numpy as np
import h5py
import argparse
from larpix.dataloader import DataLoader
from larpix.larpix import Controller
from larpixgeometry.pixelplane import PixelPlane
parse = Controller.parse_input

def fix_ADC(raw_adc):
    '''
    Converts the 8-bit value to the appropriate 6-bit value, formed by
    dropping the LSB (//2) and MSB (- 128).

    '''
    return (raw_adc - 128)//2

parser = argparse.ArgumentParser()
parser.add_argument('infile')
parser.add_argument('outfile')
args = parser.parse_args()

infile = args.infile
outfile = args.outfile
loader = DataLoader(infile)

geometry = PixelPlane.load('sensor_plane_28_simple.yaml')

numpy_arrays = []
index_limit = 10000
numpy_arrays.append(np.empty((index_limit, 9), dtype=np.float64))
current_array = numpy_arrays[-1]
current_index = 0
while True:
    block = loader.next_block()
    if block is None: break
    if block['block_type'] == 'data' and block['block_type'] == 'read':
        packets = parse(bytes(block['data']))
        for packet in packets:
            if packet.packet_type == packet.DATA_PACKET:
                current_array[current_index][0] = packet.channel_id
                current_array[current_index][1] = packet.chipid
                current_array[current_index][5] = packet.dataword
                current_array[current_index][6] = packet.timestamp
                current_array[current_index][7] = fix_ADC(packet.dataword)

                chipid = packet.chipid
                channel = packet.channel_id
                pixel = geometry.chips[chipid].channel_connections[channel]
                current_array[current_index][2] = pixel.pixelid
                current_array[current_index][3] = pixel.x
                current_array[current_index][4] = pixel.y
                current_index += 1
                if current_index == index_limit:
                    current_index = 0
                    numpy_arrays.append(np.empty((index_limit, 9),
                        dtype=np.float64))
                    current_array = numpy_arrays[-1]

numpy_arrays[-1] = numpy_arrays[-1][:current_index]
final_array = np.vstack(numpy_arrays)
with h5py.File(outfile, 'a') as outfile:
    dset = outfile.create_dataset('data', data=final_array)
    dset.attrs['descripiton'] = '''
channel id | chip id | pixel id | pixel x | pixel y | raw ADC | raw
timestamp | 6-bit ADC | full timestamp'''

