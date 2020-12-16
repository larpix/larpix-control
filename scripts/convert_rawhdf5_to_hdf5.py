import argparse
import time

import larpix
import larpix.format.rawhdf5format
import larpix.format.pacman_msg_format
import larpix.format.hdf5format
from larpix.format.rawhdf5format import from_rawfile, len_rawfile
from larpix.format.pacman_msg_format import parse
from larpix.format.hdf5format import to_file

def main(input_filename, output_filename, block_size):
    total_messages = len_rawfile(input_filename)
    total_blocks = total_messages // block_size + 1
    last = time.time()
    for i_block in range(total_blocks):
        start = i_block * block_size
        end = min(start + block_size, total_messages)
        if start == end: return

        if time.time() > last + 1:
            print('reading block {} of {}...\r'.format(i_block+1,total_blocks),end='')
            last = time.time()
        rd = from_rawfile(input_filename, start=start, end=end)
        pkts = list()
        for i_msg,data in enumerate(zip(rd['msg_headers']['io_groups'], rd['msgs'])):
            io_group,msg = data
            pkts.extend(parse(msg, io_group=io_group))
        to_file(output_filename, packet_list=pkts)
    print()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_filename', '-i', type=str, help='''Input hdf5 file, formatted with larpix.format.rawhdf5format using the larpix.io.PACMAN_IO class''')
    parser.add_argument('--output_filename', '-o', type=str, help='''Output hdf5 file,
        to be formatted with larpix.format.hdf5format''')
    parser.add_argument('--block_size', default=10240, type=int, help='''Max number of messages to store in working memory (default=%(default)s)''')
    args = parser.parse_args()
    c = main(**vars(args))
