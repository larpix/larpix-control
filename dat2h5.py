'''
A script to convert a .dat data file into the specified format with the
following data:

    channel id | chip id | pixel id | pixel x | pixel y | raw ADC | raw
    timestamp | 6-bit ADC | full timestamp

'''

from __future__ import print_function
import argparse
import numpy as np
from larpix.dataloader import DataLoader
from larpix.larpix import Controller
from larpixgeometry.pixelplane import PixelPlane
import larpixgeometry.layouts as layouts
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
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('--format', choices=['h5', 'root', 'ROOT']
args = parser.parse_args()

infile = args.infile
outfile = args.outfile
verbose = args.verbose
loader = DataLoader(infile)

if args.format == 'h5':
    import h5py
elif args.format.lower() == 'root':
    use_root = True
    import ROOT
    root_channelid = np.array([-1], dtype=int)
    root_chipid = np.array([-1], dtype=int)
    root_pixelid = np.array([-1], dtype=int)
    root_pixelx = np.array([0], dtype=float)
    root_pixely = np.array([0], dtype=float)
    root_rawADC = np.array([-1], dtype=int)
    root_rawTimestamp = np.array([0], dtype=np.uint64)
    root_ADC = np.array([-1], dtype=int)
    root_timestamp = np.array([0], dtype=np.uint64)
    fout = ROOT.TFile(outfile, 'recreate')
    ttree = ROOT.TTree('larpixdata', 'LArPixData')
    ttree.Branch('channelid', root_channelid, 'channelid/I')
    ttree.Branch('chipid', root_chipid, 'chipid/I')
    ttree.Branch('pixelid', root_pixelid, 'pixelid/I')
    ttree.Branch('pixelx', root_pixelx, 'pixelx/D')
    ttree.Branch('pixely', root_pixely, 'pixely/D')
    ttree.Branch('raw_adc', root_raw_adc, 'raw_adc/I')
    ttree.Branch('raw_timestamp', root_raw_timestamp, 'raw_timestamp/l')
    ttree.Branch('adc', root_adc, 'adc/I')
    ttree.Branch('timestamp', root_timestamp, 'timestamp/l')

geometry = PixelPlane.fromDict(layouts.load('sensor_plane_28_simple.yaml'))

numpy_arrays = []
index_limit = 10000
numpy_arrays.append(np.empty((index_limit, 9), dtype=np.float64))
current_array = numpy_arrays[-1]
current_index = 0
while True:
    block = loader.next_block()
    if block is None: break
    if block['block_type'] == 'data' and block['data_type'] == 'read':
        packets = parse(bytes(block['data']))
        for packet in packets:
            if packet.packet_type == packet.DATA_PACKET:
                current_array[current_index][0] = packet.channel_id
                current_array[current_index][1] = packet.chipid
                current_array[current_index][5] = packet.dataword
                current_array[current_index][6] = packet.timestamp
                current_array[current_index][7] = fix_ADC(packet.dataword)
                current_array[current_index][8] = 0

                chipid = packet.chipid
                channel = packet.channel_id
                pixel = geometry.chips[chipid].channel_connections[channel]
                current_array[current_index][2] = pixel.pixelid
                current_array[current_index][3] = pixel.x
                current_array[current_index][4] = pixel.y
                if use_root:
                    (root_channelid[0], root_chipid[0], root_pixelid[0],
                            root_pixelx[0], root_pixely[0],
                            root_rawADC[0], root_rawTimestamp[0],
                            root_ADC[0], root_timestamp[0]
                        ) = current_array[current_index]
                    ttree.Fill()
                else:
                    current_index += 1
                    if current_index == index_limit:
                        current_index = 0
                        numpy_arrays.append(np.empty((index_limit, 9),
                            dtype=np.float64))
                        current_array = numpy_arrays[-1]

if use_root:
    ttree.Write()
    fout.Write()
    fout.Close()
else:
    numpy_arrays[-1] = numpy_arrays[-1][:current_index]
    final_array = np.vstack(numpy_arrays)
    with h5py.File(outfile, 'w') as outfile:
        dset = outfile.create_dataset('data', data=final_array)
        dset.attrs['descripiton'] = '''
    channel id | chip id | pixel id | pixel x | pixel y | raw ADC | raw
    timestamp | 6-bit ADC | full timestamp'''

