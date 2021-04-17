#!/usr/env/bin python3
'''
Usage
=====
To merge larpix raw-formatted hdf5 files together::

    rawhdf5_tool.py --merge -i <files to merge, in order> -o <destination filename>

To split a single larpix raw-formatted hdf5 file into many::

    rawhdf5_tool.py --split -i <file to split> -o <destination directory> --max_length=<dataset length to split>

> Note:
>
> When merging files, there is the possibility of losing file metadata that is
> necessary to parse the file. The merge behavior will only keep the metadata of each
> dataset coming from the first file. It is highly recommended that you only
> `merge` files that were `split` using this utility, or files where the metadata
> guaranteed to be the same (i.e. many files of the same simulation run).

'''
import h5py
import warnings
import os
try:
    from tqdm import tqdm
    _has_tqdm = True
except Exception as e:
    warnings.warn(e)
    _has_tqdm = False

_default_max_length = -1
_default_block_size = 102400

def merge_files(input_filenames, output_filename, block_size):
    with h5py.File(output_filename, 'w', libver='latest') as fo:
        curr_idx = 0
        prev_idx = 0
        for i,input_filename in enumerate(input_filenames):
            print(input_filename, '{}/{}'.format(i+1, len(input_filenames)))
            with h5py.File(input_filename, 'r', libver='latest', swmr=True) as fi:
                if i == 0:
                    # create datasets and groups
                    fo.create_group('meta')
                    fo.create_dataset('msgs', shape=fi['msgs'].shape, maxshape=(None,), compression='gzip', dtype=fi['msgs'].dtype)
                    fo.create_dataset('msg_headers', shape=fi['msg_headers'].shape, maxshape=(None,), compression='gzip', dtype=fi['msg_headers'].dtype)

                    # copy meta data
                    for attr,value in fi['meta'].attrs.items():
                        fo['meta'].attrs[attr] = value
                else:
                    # resize datasets
                    fo['msgs'].resize((len(fo['msgs']) + len(fi['msgs']),))
                    fo['msg_headers'].resize((len(fo['msg_headers']) + len(fi['msg_headers']),))

                # copy data in chunks
                for start in tqdm(range(0, len(fi['msgs']), block_size)) if _has_tqdm else range(0, len(fi['msgs']), block_size):
                    end = min(start+block_size, len(fi['msgs']))
                    prev_idx = curr_idx
                    curr_idx += end - start
                    fo['msgs'][prev_idx:curr_idx] = fi['msgs'][start:end]
                    fo['msg_headers'][prev_idx:curr_idx] = fi['msg_headers'][start:end]
    return

def split_file(input_filename, output_directory, max_length, block_size):
    with h5py.File(input_filename, 'r', libver='latest', swmr=True) as fi:
        output_filename_fmt = os.path.join(output_directory, os.path.basename(input_filename)[:-2]) + '{}.h5'

        i = 0
        curr_idx, prev_idx = 0, 0
        fo = None

        try:
            for start in tqdm(range(0, len(fi['msgs']), block_size)) if _has_tqdm else range(0, len(fi['msgs']), block_size):
                end = min(start+block_size, len(fi['msgs']))

                if fo is None or (os.stat(output_filename).st_size >= max_length and max_length > 0):
                    # open next file
                    if fo is not None:
                        fo.close()
                    output_filename = output_filename_fmt.format(i)
                    fo = h5py.File(output_filename, 'a', libver='latest')
                    i += 1
                    curr_idx, prev_idx = 0, 0

                    # create datasets and groups
                    fo.create_group('meta')
                    fo.create_dataset('msgs', shape=(0,), maxshape=(None,), compression='gzip', dtype=fi['msgs'].dtype)
                    fo.create_dataset('msg_headers', shape=(0,), maxshape=(None,), compression='gzip', dtype=fi['msg_headers'].dtype)

                    # copy meta data
                    for attr,value in fi['meta'].attrs.items():
                        fo['meta'].attrs[attr] = value

                    fo.swmr_mode = True

                # resize datasets
                prev_idx = curr_idx
                curr_idx += end - start
                fo['msgs'].resize((curr_idx,))
                fo['msg_headers'].resize((curr_idx,))

                # copy data
                fo['msgs'][prev_idx:curr_idx] = fi['msgs'][start:end]
                fo['msg_headers'][prev_idx:curr_idx] = fi['msg_headers'][start:end]

                fo['msgs'].flush()
                fo['msg_headers'].flush()
        except:
            raise
        finally:
            if fo is not None:
                fo.close()
    return

def main(input_filenames, output_filename, max_length=_default_max_length, block_size=_default_block_size, **kwargs):
    if kwargs.get('merge', False):
        merge_files(
            input_filenames, output_filename,
            block_size=block_size
            )
    elif kwargs.get('split', False):
        split_file(
            input_filenames[0], output_filename,
            max_length=max_length, block_size=block_size
            )
    else:
        print('No action specified, exiting.')

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-i', nargs='+', required=True, help='Input file(s)')
    parser.add_argument('-o', required=True, type=str, help='Output file or directory')
    parser.add_argument('--max_length', type=int, default=_default_max_length, required=False, help='Max dataset length (split only, default=%(default)s bytes)')
    parser.add_argument('--block_size', type=int, default=_default_block_size, required=False, help='Block size used for reads (default=%(default)s)')
    parser.add_argument('--merge', action='store_true', help='Flag to merge files')
    parser.add_argument('--split', action='store_true', help='Flag to split files')
    args = parser.parse_args()
    main(
        input_filenames=args.i,
        output_filename=args.o,
        **vars(args)
        )
