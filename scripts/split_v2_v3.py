#!/usr/bin/env python3

"""Split a binary file into LArPix-v2 and LArPix-v3 files"""

import argparse
from pathlib import Path

import h5py
import numpy as np

IOGS_V2 = [1, 2, 5, 6]
IOGS_V3 = [3, 4]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inpath')
    args = ap.parse_args()
    
    inpath = Path(args.inpath)
    outpath_v2 = inpath.parent / (inpath.stem + '.v2.h5')
    outpath_v3 = inpath.parent / (inpath.stem + '.v3.h5')

    infile = h5py.File(inpath)

    for iogs, outpath in [(IOGS_V2, outpath_v2), (IOGS_V3, outpath_v3)]:
        with h5py.File(outpath, 'w') as outf:
            outf['daq_configs'] = infile['daq_configs'][:]
            outf['meta'] = infile['meta'][:]
            mask = np.zeros(len(outf['msgs']), dtype=bool)
            for iog in iogs:
                mask |= infile['msg_headers']['io_groups'] == iog
            outf['msg_headers'] = infile['msg_headers'][:][mask]
            outf['msgs'] = infile['msgs'][:][mask]


if __name__ == '__main__':
    main()
