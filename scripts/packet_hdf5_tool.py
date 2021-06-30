#!/usr/env/bin python3
'''
Usage
=====
To merge larpix packet-formatted hdf5 files together::

    packethdf5_tool.py --merge -i <files to merge, in order> -o <destination filename>

> Note:
>
> When merging files, there is the possibility of losing some file meta data. The
> merge behavior will only keep the metadata of each dataset coming from the first
> file. It is highly recommended that you only `merge` files where the metadata
> guaranteed to be the same (i.e. many files of the same simulation run).

'''
import h5py
import warnings
import os
try:
    from tqdm import tqdm
    _has_tqdm = True
except Exception as e:
    warnings.warn(str(e), RuntimeWarning)
    _has_tqdm = False

_default_max_length = -1
_default_block_size = 102400

def move_dataset(input_file, output_file, dset_name, block_size):
    curr_idx = len(output_file[dset_name])

    mc_assn_flag =  dset_name == 'mc_packets_assn'
    mc_offset = curr_idx

    output_file[dset_name].resize((len(output_file[dset_name]) + len(input_file[dset_name]),))
    # copy data in chunks
    for start in tqdm(range(0, len(input_file[dset_name]), block_size)) if _has_tqdm else range(0, len(input_file[dset_name]), block_size):
        end = min(start+block_size, len(input_file[dset_name]))
        prev_idx = curr_idx
        curr_idx += end - start

        if mc_assn_flag:
            # special case for mc packets associations, add offset since start of dataset to track_ids
            data = input_file[dset_name][start:end]
            data['track_ids'] += mc_offset
            output_file[dset_name][prev_idx:curr_idx] = data
        else:
            output_file[dset_name][prev_idx:curr_idx] = input_file[dset_name][start:end]

def merge_files(input_filenames, output_filename, block_size):
    with h5py.File(output_filename, 'w') as fo:
        for i,input_filename in enumerate(input_filenames):
            print(input_filename, '{}/{}'.format(i+1, len(input_filenames)))
            with h5py.File(input_filename, 'r') as fi:
                if i == 0:
                    # create datasets and groups
                    #fo.create_group('_header')
                    for grp_name in fi.keys():
                        if isinstance(fi[grp_name], h5py.Group):
                            fo.copy(fi[grp_name], grp_name)

                    # create datasets
                    for dset_name in fi.keys():
                        if isinstance(fi[dset_name], h5py.Dataset):
                            fo.create_dataset(dset_name, shape=(0,), maxshape=(None,), compression='gzip', dtype=fi[dset_name].dtype)

                        # copy meta data
                        for attr,value in fi[dset_name].attrs.items():
                            fo[dset_name].attrs[attr] = value

                # copy data
                for dset_name in fo.keys():
                    if isinstance(fo[dset_name], h5py.Dataset):
                        print('copying',dset_name,'...')
                        move_dataset(fi, fo, dset_name, block_size)


def main(input_filenames, output_filename, max_length=_default_max_length, block_size=_default_block_size, **kwargs):
    if kwargs.get('merge', False):
        merge_files(
            input_filenames, output_filename,
            block_size=block_size
            )
    else:
        print('No action specified, exiting.')

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-i', nargs='+', required=True, help='Input file(s)')
    parser.add_argument('-o', required=True, type=str, help='Output file')
    parser.add_argument('--block_size', type=int, default=_default_block_size, required=False, help='Block size used for reads (default=%(default)s)')
    parser.add_argument('--merge', action='store_true', help='Flag to merge files')
    args = parser.parse_args()
    main(
        input_filenames=args.i,
        output_filename=args.o,
        **vars(args)
        )
