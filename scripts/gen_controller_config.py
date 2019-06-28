#!/usr/bin/env python
'''
This script allows you to easily generate a controller configuration file based
on the larpix chip key interface.
Generally, this script can generate string-based keys that contain the chip_id,
io channel, and io group within the key. The characters $, {, and } are reserved for special
functions and should not be used within keys. To use:
python gen_controller_config.py --name <config name> --key_fmt <formatting strings> --outfile <output file config file>

The formatting string is used to generate chip keys, generally it is a list of
strings that specify chip keys. Using ${} special functions allow you to
generate chip keys according to a integer list. For example:
 - --key_fmt 'test-${0-2}' generate 3 chip keys (test-0, test-1, test-2)
 - --key_fmt 'test-${0,1,2}' generates the same
 - --key_fmt 'test-${0-1,2}' also generates the same
For more complex chip keys that have repeated sets of identical chip ids, you
can use multiple instances of the ${} special function. This operates with the
same syntax. For example:
 - --key_fmt 'test-${0-2}-${0}' generates 5 chip keys (test-0-0, test-1-0,
   test-2-0)
 - --key_fmt 'test-${0-2}-${0,1}' generates 6 chip keys (test-0-0, test-0-1,
 test-1-0, test-1-1, test-2-0, test-2-1)
Finally, the --key_fmt argument can be passed multiple strings to generate a
variety of chip key formats:
 - --key_fmt 'key-0-${0-2}' 'key-1-${2-4}' 'diff-${0-2}' generates 9 chip keys
   (key-0-0, key-0-1, key-0-2, key-1-2, key-1-3, key-1-4, diff-0, diff-1,
   diff-2)

'''
import argparse
import os
import json
from itertools import zip_longest

from larpix import configs
import larpix

parser = argparse.ArgumentParser(usage=__doc__)
parser.add_argument('--name', '-n', type=str, required=True, help='''
    configuration name (required)
    ''')
parser.add_argument('--key_fmt', '-k', type=str, required=True, nargs='+',
    help='''
    key formatting specifier (required)
    see general help for more information
    ''')
parser.add_argument('--outfile', '-o', type=str, required=False, default=None,
    help='''
    output filename (optional, default=<name>_chip_info.json)
    if file exists, chip keys will be appended to the config file
    ''')
# parser.add_argument('--io', type=str, required=False, default=None, help='''
#     io class to validate generated keys against (optional, default=%(default)s)
#     path should be relative to the larpix.io module, e.g. 'zmq_io.ZMQ_IO' is a
#     valid path specifier
#     ''')
args = parser.parse_args()

# Load up arguments
name = args.name
key_fmts = args.key_fmt
# if not all([key_fmt.count('$[') == 1 for key_fmt in key_fmts]):
#     raise RuntimeError('A single chip key must be specified in each key formatting string')
outfile = args.outfile
if outfile is None:
    outfile = '{}_chip_info.json'.format(name)
io = None
if not io is None:
    module_str = args.io.split('.')
    io_module = None
    if len(module_str) > 1:
        io_module = __import__('larpix.io.'+'.'.join(module_str[:-1]), fromlist=[module_str[-1]])
    else:
        io_module = __import__('larpix.io', fromlist=[module_str[-1]])
    io = getattr(io_module, module_str[-1])

# Load existing configuration
configuration = {}
if os.path.exists(outfile):
    with open(outfile,'r') as ifile:
        configuration = json.load(ifile)
    if not io is None and 'chip_list' in configuration.keys():
        for chip_key, chip_id in configuration['chip_list']:
            if not io.is_valid_chip_key(chip_key):
                raise RuntimeError('Previous configuration file key \'{}\' is incompatible with io  {}'.format(chip_key, io))
else:
    print('No existing file {} found, generating from scratch...'.format(outfile))

# Declare helper functions
def append_chip_ids(sub_keys, chip_id_fmt):
    '''
    Appends all specified chip_ids to subkey strings
    Specification of chip_ids follows 2,4,5-7 = [2,4,5,6,7]
    Returns all new subkeys along with associated chip ids as a 2-tuple

    '''
    return_keys = []
    return_ids = []
    chip_id_sub_strs = chip_id_fmt.split(',')
    for chip_id_sub_str in chip_id_sub_strs:
        chip_id_spec = chip_id_sub_str.split('-')
        if len(chip_id_spec) == 2:
            chip_ids  = range(int(chip_id_spec[0]), int(chip_id_spec[1])+1)
            for chip_id in chip_ids:
                for sub_key in sub_keys:
                    return_keys += [sub_key + str(chip_id)]
                    return_ids += [chip_id]
        else:
            for sub_key in sub_keys:
                return_keys += [sub_key + str(int(chip_id_spec[0]))]
                return_ids += [int(chip_id_spec[0])]
        # print('end loop chip_id', chip_id_sub_str, return_keys, return_ids)
    return return_keys, return_ids

def append_int(sub_keys, chip_ids, int_fmt):
    '''
    Appends all specified integers to subkey strings
    Specification of integers follows 2,4,5-7 = [2,4,5,6,7]
    Returns all new subkeys along with associated chip ids as a 2-tuple

    '''
    return_keys = []
    return_ids = []
    int_sub_strs = int_fmt.split(',')
    for int_sub_str in int_sub_strs:
        int_spec = int_sub_str.split('-')
        if len(int_spec) == 2:
            ints = range(int(int_spec[0]), int(int_spec[1])+1)
            for integer in ints:
                # print(sub_keys)
                # print(chip_ids)
                for sub_key, chip_id in zip_longest(sub_keys, chip_ids):
                    return_keys += [sub_key + str(integer)]
                    # print(return_keys)
                    if chip_ids:
                        return_ids += [chip_id]
        else:
            for sub_key, chip_id in zip_longest(sub_keys, chip_ids):
                return_keys += [sub_key + str(int(int_spec[0]))]
                if chip_ids:
                    return_ids += [chip_id]
        # print('end loop int', int_sub_str, return_keys, return_ids)
    return return_keys, return_ids

def multi_split(strings, delimiters=[' ','\t','\n']):
    '''
    Recursively splits a list of strings according to a list of delimiters
    E.g. multi_split(['test, word1', ', word2'],delimiters=[',',' ']) returns
    ['test','word1','word2']

    '''
    if len(delimiters) == 1:
        return_strings = []
        for string in strings:
            return_strings += string.split(delimiters[0])
        return return_strings
    else:
        return_strings = strings
        for delimiter in delimiters:
            return_strings = multi_split(return_strings, delimiter)
        return return_strings

def generate_keys(key_fmt):
    '''
    Generates all possible chip keys and chip ids based on string formatter

    '''
    return_keys = ['']
    return_ids = []

    # print(key_fmt)
    # str_segments = multi_split([key_fmt], delimiters=['$',']','}'])
    str_segments = multi_split([key_fmt], delimiters=['$','}'])
    # print(str_segments)
    for str_seg in str_segments:
        if not str_seg:
            continue
        # if str_seg[0] == '[':
        #     return_keys, return_ids = append_chip_ids(return_keys, str_seg[1:])
        if str_seg[0] == '{':
            return_keys, return_ids = append_int(return_keys, return_ids, str_seg[1:])
        elif return_keys:
            for idx, key in enumerate(return_keys):
                new_key = key + str_seg
                return_keys[idx] = new_key
        # print('end loop', str_seg, return_keys, return_ids)
    return return_keys, return_ids

# Initialize
configuration['name'] = name
if not 'chip_list' in configuration.keys():
    configuration['chip_list'] = []
# Generate keys
for key_fmt in key_fmts:
    chip_keys, chip_ids = generate_keys(key_fmt)
    # for chip_key, chip_id in zip(chip_keys, chip_ids):
    for chip_key in chip_keys:
        # Check if key is valid for io class
        if not io is None:
            if not io.is_valid_chip_key(chip_key):
                raise RuntimeError('Format specifier led to an invalid chip key \'{}\''.format(chip_key))
        # Check if chip_key is unique (overwrite chip id, if exists)
        existing_keys = [chip_key for chip_key in configuration['chip_list']]
        if chip_key in existing_keys:
            idx = list(zip(*configuration['chip_list']))[0].index(chip_key)
            configuration['chip_list'][idx] = chip_key
        else:
            configuration['chip_list'].append(chip_key)

# Save
with open(outfile, 'w') as of:
    json.dump(configuration, of, indent=4)

