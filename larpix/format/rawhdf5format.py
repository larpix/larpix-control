'''
This is an alternative to the ``larpix.format.hdf5format``format that allows for
much faster conversion to file at the expense of human readability.

To use, pass a list of bytestring messages into the ``to_rawfile()`` method::

    msgs = [b'this is a test message', b'this is a different message']
    to_rawfile('raw.h5', msgs)

To access the data in the file, the inverse method ``from_rawfile()`` is used::

    rd = from_rawfile('raw.h5')
    rd['msgs'] # [b'this is a test message', b'this is a different message']

Message may be recieved from multiple ``io_group`` sources, in this case, a
per-message ``io_group`` can be specified as a list of integers of the same
length as the ``msgs`` list and passed into the file at the same time::

    msgs = [b'message from 1', b'message from 2']
    io_groups = [1, 2]
    to_rawfile('raw.h5', msgs=msgs, io_groups=io_groups)

    rd = from_rawfile('raw.h5')
    rd['msgs'] # [b'message from 1', b'message from 2']
    rd['io_groups'] # [1, 2]

This format was created with a specific application in mind - provide a
temporary but fast file format for PACMAN messages. When used in this
case, to convert to the standard ``larpix.format.hdf5format``::

    from larpix.format.pacman_msg_format import parse
    from larpix.format.hdf5format import to_file

    rd = from_rawfile('raw.h5')
    pkts = list()
    for io_group,msg in zip(rd['io_groups'], rd['msgs']):
        pkts.extend(parse(msg, io_group=io_group))
    to_file('new_filename.h5', packet_list=pkts)

but as always, the most efficient means of accessing the data is to operate on
the data itself, rather than converting between types.

Metadata (v0.0)
---------------
The group ``meta`` contains file metadata stored as attributes:

    - ``created``: ``float``, unix timestamp since the 1970 epoch in seconds indicating when file was first created

    - ``modified``: ``float``, unix timestamp since the 1970 epoch in seconds indicating when the file was last written to

    - ``version``: ``str``, file version, formatted as ``'major.minor'``

Datasets (v0.0)
---------------
The hdf5 format contains two datasets ``msgs`` and ``io_groups``:

    - ``msgs``: shape ``(N,)``; variable-length ``uint1`` arrays representing each message

    - ``io_groups``: shape ``(N,)``; ``uint1`` array representing the ``io_group`` associated with each message

'''
import time
import warnings

import h5py
import numpy as np

#: Most up-to-date raw larpix hdf5 format version.
latest_version = '0.0'

#: Description of the datasets and their dtypes used in each version of the raw larpix hdf5 format.
#:
#: Structured as ``dataset_dtypes['<version>']['<dataset>'] = <dtype>``.
dataset_dtypes = {
    '0.0': {
        'msgs': h5py.vlen_dtype(np.dtype('u1')),
        'io_groups': np.dtype('u1')
    }
}
def _store_msgs_v0_0(msgs, version):
    msg_dtype = np.dtype('u1')
    arr_dtype = dataset_dtypes[version]['msgs']
    return np.array([np.frombuffer(msg, dtype=msg_dtype) for msg in msgs], dtype=arr_dtype)

def _store_io_groups_v0_0(io_groups, version):
    return np.array(io_groups, dtype=dataset_dtypes[version]['io_groups'])

def _parse_msgs_v0_0(msgs, version):
    return [msg.tobytes() for msg in msgs]

def _parse_io_groups_v0_0(io_groups, version):
    return list(io_groups.astype(int))

def _store_msgs(msgs, version):
    '''
    A version-safe way to put messages into the dataset

    :param msgs: an iterable of PACMAN messages to convert

    :param version: version string

    :returns: a numpy array, 1 row for each msg

    '''
    return _store_msgs_v0_0(msgs, version)

def _store_io_groups(io_groups, version):
    '''
    A version-safe way to put io_groups into the dataset

    :param msgs: an iterable of io_groups to convert to a numpy array

    :param version: version string

    :returns: a numpy array, 1 row for each io_group

    '''
    return _store_io_groups_v0_0(io_groups, version)

def _parse_msgs(msgs, version):
    '''
    A version-safe conversion of numpy array void objects into PACMAN message byte strings

    :param msgs: a list of void-type numpy arrays

    :param version: version string

    :returns: list of PACMAN message byte strings, 1 for each row in data
    '''
    return _parse_msgs_v0_0(msgs, version)

def _parse_io_groups(io_groups, version):
    '''
    A version-safe conversion of io_groups numpy array to an io_groups list

    :param msgs: an io_groups array to convert to a list of io_groups

    :param version: version string

    :returns: list of io_groups, 1 for each row in data
    '''
    return _parse_io_groups_v0_0(io_groups, version)

def to_rawfile(filename, msgs=None, version=None, io_groups=None):
    '''
    Write a list of bytestring messages to an hdf5 file. If the file exists,
    the messages will appended to the end of the dataset.

    :param filename: desired filename for the file to write or update

    :param msgs: iterable of variable-length bytestrings to write to the file. If ``None`` specified, will only create file and update metadata.

    :param version: a string of major.minor version desired. If ``None`` specified, will use the latest file format version (if new file) or version in file (if updating an existing file).

    :param io_groups: iterable of io_groups to associate with each message. If ``None`` specified, will use a default value of ``0`` for each message.

    '''
    now = time.time()
    with h5py.File(filename, 'a', libver='latest') as f:
        if 'meta' not in f.keys():
            # new file
            version = latest_version if version is None else version
            f.create_group('meta')
            f['meta'].attrs['version'] = version
            f['meta'].attrs['created'] = now
            f['meta'].attrs['modified'] = now

            # get current position in file
            curr_idx = 0

            # create datasets
            f.create_dataset('msgs', shape=(0,), maxshape=(None,), compression='gzip', dtype=dataset_dtypes[version]['msgs'])
            f.create_dataset('io_groups', shape=(0,), maxshape=(None,), compression='gzip', dtype=dataset_dtypes[version]['io_groups'])

            f.swmr_mode = True
        else:
            # existing file
            file_version = f['meta'].attrs['version']
            assert (file_version == version) or (version is None), 'Version mismatch! file: {}, requested: {}'.format(file_version, version)
            version = file_version

            f.swmr_mode = True

            f['meta'].attrs['modified'] = now

        # update data
        if msgs is not None:
            io_groups = io_groups if io_groups is not None else np.zeros(len(msgs))
            assert len(io_groups) == len(msgs), 'Data length mismatch! msgs is length {}, but io_groups is length {}'.format(len(msgs),len(io_groups))

            # resize datasets
            curr_idx = len(f['msgs'])
            f['msgs'].resize((curr_idx+len(msgs),))
            f['io_groups'].resize((curr_idx+len(io_groups),))

            # store in file
            msgs_array = _store_msgs(
                msgs,
                version=version
                )
            io_groups_array = _store_io_groups(
                io_groups,
                version=version
                )

            f['msgs'][curr_idx:curr_idx + len(msgs_array)] = msgs_array
            f['io_groups'][curr_idx:curr_idx + len(io_groups_array)] = io_groups_array

        # flush
        f['msgs'].flush()
        f['io_groups'].flush()

def _synchronize(attempts, *dsets):
    if len(dsets) <= 1:
        return
    success = attempts != 0
    attempt = 1
    lengths = [0]*len(dsets)
    while (attempt <= attempts or attempts < 0) and not success:
        attempt += 1
        for i,dset in enumerate(dsets):
            dset.id.refresh()
            lengths[i] = len(dset)
        if all([lengths[0] == length for length in lengths[1:]]):
            success = True
    if not success:
        raise RuntimeError('Could not achieve a stable file state after {} attempts!'.format(attempts))

def len_rawfile(filename, attempts=1):
    '''
    Check the total number of messages in a file

    :param filename: filename to check

    :param attempts: a parameter only relevant if file is being actively written to by another process, specifies number of refreshes to try if a synchronized state between the datasets is not achieved. A value less than ``0`` busy blocks until a synchronized state is achieved. A value greater than ``0`` tries to achieve synchronization a max of ``attempts`` before throwing a ``RuntimeError``. And a value of ``0`` does not attempt to synchronize

    :returns: ``int`` number of messages in file

    '''
    with h5py.File(filename, 'r', swmr=True, libver='latest') as f:
        _synchronize(attempts, f['msgs'], f['io_groups'])
        return len(f['msgs'])

def from_rawfile(filename, start=None, end=None, version=None, attempts=1):
    '''
    Read a chunk of bytestring messages from an existing file

    :param filename: filename to read bytestrings from

    :param version: required version compatibility. If ``None`` specified, uses the version stored in the file metadata

    :param start: index for the start position when reading from the file (default = ``None``). If a value less than 0 is specified, index is relative to the end of the file. If ``None`` is specified, data is read from the start of the file.

    :param end: index for the end position when reading from the file (default = ``None``). If a value less than 0 is specified, index is relative to the end of the file. If ``None`` is specified, data is read until the end of the file.

    :param attempts: a parameter only relevant if file is being actively written to by another process, specifies number of refreshes to try if a synchronized state between the datasets is not achieved. A value less than ``0`` busy blocks until a synchronized state is achieved. A value greater than ``0`` tries to achieve synchronization a max of ``attempts`` before throwing a ``RuntimeError``. And a value of ``0`` does not attempt to synchronize

    :returns: ``dict`` with keys for ``'created'``, ``'modified'``, and ``'version'`` metadata, along with ``'msgs'`` (a ``list`` of bytestring messages) and ``'io_groups'`` (a ``list`` of ``int``)

    '''
    with h5py.File(filename, 'r', swmr=True, libver='latest') as f:
        # fetch metadata
        created = f['meta'].attrs['created']
        modified = f['meta'].attrs['modified']
        file_version = f['meta'].attrs['version']
        version_major = file_version.split('.')[0]
        assert (version is None) or (file_version >= version and version_major == version.split('.')[0]), 'Incompatible version mismatch! file: {}, requested: {}'.format(file_version, version)
        version_minor = min(file_version.split('.')[-1], version.split('.')[-1]) if version is not None else file_version.split('.')[-1]
        version = '{}.{}'.format(version_major,version_minor)

        # check to make sure that the msgs and io_groups dsets are synchronized
        _synchronize(attempts, f['msgs'], f['io_groups'])

        # define chunk of data to load
        start = int(start) if start is not None else 0
        end = int(end) if end is not None else len(f['msgs'])

        # get data from file
        msgs = _parse_msgs(f['msgs'][start:end], version)
        io_groups = _parse_io_groups(f['io_groups'][start:end], version)

        return dict(
            created=created,
            modified=modified,
            version=version,
            msgs=msgs,
            io_groups=io_groups
            )
