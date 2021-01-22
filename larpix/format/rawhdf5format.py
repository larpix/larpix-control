'''
This is an alternative to the ``larpix.format.hdf5format``format that allows for
much faster conversion to file at the expense of human readability.

To use, pass a list of bytestring messages into the ``to_rawfile()`` method::

    msgs = [b'this is a test message', b'this is a different message']
    to_rawfile('raw.h5', msgs)

To access the data in the file, the inverse method ``from_rawfile()`` is used::

    rd = from_rawfile('raw.h5')
    rd['msgs'] # [b'this is a test message', b'this is a different message']

Messages may be recieved from multiple ``io_group`` sources, in this case, a
per-message header with ``io_group`` can be specified as a list of integers of
the same length as the ``msgs`` list and passed into the file at the same time::

    msgs = [b'message from 1', b'message from 2']
    io_groups = [1, 2]
    to_rawfile('raw.h5', msgs=msgs, msg_headers={'io_groups': io_groups})

    rd = from_rawfile('raw.h5')
    rd['msgs'] # [b'message from 1', b'message from 2']
    rd['msg_headers']['io_groups'] # [1, 2]

File versioning
---------------

Some version validation is included with the file format through
the ``version`` and ``io_version`` file metadata. When creating a new file, a
file format version can be provided with the ``version`` keyword argument as
a string formatted ``'major.minor'``::

    to_rawfile('raw_v0_0.h5', version='0.0')

Subsequent writes to the file will only occur if the requested file version and
the existing file versions are compatible. Incompatiblity occurs if there is
a difference in the major version number or the minor version number is less
than the requested file version::

    to_rawfile('raw_v0_0.h5', version='0.1') # fails due to minor version incompatibility
    to_rawfile('raw_v0_0.h5', version='1.0') # fails due to major version incompatibility

By default, the most recent file version is used.

On the file read side, a version number can be requested and the file will be
parsed assuming a specific version::

    from_rawfile('raw_v0_0.h5', version='0.0')
    from_rawfile('raw_v0_0.h5', version='0.1') # fails due to minor version incompatiblity
    from_rawfile('raw_v0_0.h5', version='1.0') # fails due to major version compatibility

The ``io_version`` optional metadata marks the version of the io message format
that was used to encode the message bytestrings. If present as a keyword
argument when writing to the file, an ``AssertionError`` will be raised if
the io version is incompatible with the existing one stored in metadata::

    to_rawfile('raw_io_v0_0.h5', io_version='0.0')
    to_rawfile('raw_io_v0_0.h5', io_version='0.1') # fails due to minor version incompatibility
    to_rawfile('raw_io_v0_0.h5', io_version='1.0') # fails due to major version incompatibility

A similar mechanism occurs when requesting an io version when reading from the
file::

    from_rawfile('raw_io_v0_0.h5', io_version='0.1') # fails due to minor version incompatibility
    from_rawfile('raw_io_v0_0.h5', io_version='1.0') # fails due to major version
    from_rawfile('raw_io_v0_0.h5', io_version='0.0')

I think it is worthwhile to further clarify the ``io_version`` and the file
``version``, as this might be confusing. In particular, you might be asking,
"What io versions are compatible with what file versions?" The ``rawhdf5format``
is a way of wrapping raw binary data into a format that only requires HDF5 to
parse. The file version represents this HDF5 structuring (the hdf5 dataset
formats, file metadata, what message header data is available). Whereas the
``io_version`` represents the formatting of the binary data that the file
contains. So the answer to that question is: *all* file versions are compatible
with *all* io versions.

Converting to other file types
------------------------------

This format was created with a specific application in mind - provide a
temporary but fast file format for PACMAN messages. When used in this
case, to convert to the standard ``larpix.format.hdf5format``::

    from larpix.format.pacman_msg_format import parse
    from larpix.format.hdf5format import to_file

    rd = from_rawfile('raw.h5')
    pkts = list()
    for io_group,msg in zip(rd['msg_headers']['io_groups'], rd['msgs']):
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

    - ``io_version``: ``str``, optional version for message bytestring encoding, formatted as ``'major.minor'``

Datasets (v0.0)
---------------
The hdf5 format contains two datasets ``msgs`` and ``msg_headers``:

    - ``msgs``: shape ``(N,)``; variable-length ``uint1`` arrays encoding each message bytestring

    - ``msg_headers``: shape ``(N,)``; numpy structured array with fields:

        - ``'io_group'``: ``uint1`` representing the ``io_group`` associated with each message

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
        'msg_headers': np.dtype([
            ('io_groups','u1')
            ])
    }
}
def _store_msgs_v0_0(msgs, version):
    msg_dtype = np.dtype('u1')
    arr_dtype = dataset_dtypes[version]['msgs']
    return np.array([np.frombuffer(msg, dtype=msg_dtype) for msg in msgs], dtype=arr_dtype)

def _store_msg_headers_v0_0(msg_headers, version):
    length = len(msg_headers['io_groups'])
    arr = np.zeros((length,), dtype=dataset_dtypes[version]['msg_headers'])
    for key in msg_headers:
        arr[key] = msg_headers[key]
    return arr

def _parse_msgs_v0_0(msgs, version):
    return [msg.tobytes() for msg in msgs]

def _parse_msg_headers_v0_0(msg_headers, version):
    rd = dict()
    for key in msg_headers.dtype.names:
        rd[key] = list(msg_headers[key].astype(int))
    return rd

def _store_msgs(msgs, version):
    '''
    A version-safe way to put messages into the dataset

    :param msgs: an iterable of PACMAN messages to convert

    :param version: version string

    :returns: a numpy array, 1 row for each msg

    '''
    return _store_msgs_v0_0(msgs, version)

def _store_msg_headers(msg_headers, version):
    '''
    A version-safe way to put message headers into the dataset

    :param msg_headers: a dict of iterable values for each field in ``dataset_dtypes[version]['msg_headers'].names`` to convert to a numpy array

    :param version: version string

    :returns: a numpy array, 1 row for each io_group

    '''
    return _store_msg_headers_v0_0(msg_headers, version)

def _parse_msgs(msgs, version):
    '''
    A version-safe conversion of numpy array void objects into PACMAN message byte strings

    :param msgs: a list of void-type numpy arrays

    :param version: version string

    :returns: list of PACMAN message byte strings, 1 for each row in data
    '''
    return _parse_msgs_v0_0(msgs, version)

def _parse_msg_headers(msg_headers, version):
    '''
    A version-safe conversion of message header numpy arrays into lists

    :param msg_headers: a structure array of the msg_header dataset to convert to a list of values

    :param version: version string

    :returns: dict of lists, keyed by dtype fields, 1 entry in each list for each row in data
    '''
    return _parse_msg_headers_v0_0(msg_headers, version)

def to_rawfile(filename, msgs=None, version=None, msg_headers=None, io_version=None):
    '''
    Write a list of bytestring messages to an hdf5 file. If the file exists,
    the messages will appended to the end of the dataset.

    :param filename: desired filename for the file to write or update

    :param msgs: iterable of variable-length bytestrings to write to the file. If ``None`` specified, will only create file and update metadata.

    :param version: a string of major.minor version desired. If ``None`` specified, will use the latest file format version (if new file) or version in file (if updating an existing file).

    :param msg_headers: a dict of iterables to associate with each message header. Iterables must be same length as ``msgs``. If ``None`` specified, will use a default value of ``0`` for each message. Keys are dtype field names specified in ``dataset_dtypes[version]['msg_headers'].names``

    :param io_version: optional metadata to associate with file corresponding to the io format version of the bytestring messages. Throws ``RuntimeError`` if version incompatibility encountered in an existing file.

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
            if io_version is not None:
                f['meta'].attrs['io_version'] = io_version

            # get current position in file
            curr_idx = 0

            # create datasets
            f.create_dataset('msgs', shape=(0,), maxshape=(None,), compression='gzip', dtype=dataset_dtypes[version]['msgs'])
            f.create_dataset('msg_headers', shape=(0,), maxshape=(None,), compression='gzip', dtype=dataset_dtypes[version]['msg_headers'])

            f.swmr_mode = True
        else:
            # existing file
            file_version = f['meta'].attrs['version']
            assert (file_version == version) or (version is None), 'Version mismatch! file: {}, requested: {}'.format(file_version, version)
            version = file_version
            assert (io_version is None) or ('io_version' in f['meta'].attrs.keys() and f['meta'].attrs['io_version'].split('.')[0] == io_version.split('.')[0] and f['meta'].attrs['io_version'].split('.')[-1] >= io_version.split('.')[-1]), 'IO version mismatch! file: {}, requested {}'.format(f['meta'].attrs['io_version'],io_version)

            f.swmr_mode = True

            f['meta'].attrs['modified'] = now

        # update data
        if msgs is not None:
            headers = dict()
            for key in msg_headers:
                headers[key] = msg_headers[key]
                if key not in dataset_dtypes[version]['msg_headers'].names:
                    raise RuntimeError('Encountered unknown message header key {}'.format(key))
            for key in dataset_dtypes[version]['msg_headers'].names:
                if key not in headers:
                    headers[key] = np.zeros(len(msgs))
                assert len(headers[key]) == len(msgs), 'Data length mismatch! msgs is length {}, but msg_headers field {} is length {}'.format(len(msgs),key,len(headers[key]))

            # resize datasets
            curr_idx = len(f['msgs'])
            f['msgs'].resize((curr_idx+len(msgs),))
            f['msg_headers'].resize((curr_idx+len(msgs),))

            # store in file
            msgs_array = _store_msgs(
                msgs,
                version=version
                )
            msg_headers_array = _store_msg_headers(
                msg_headers,
                version=version
                )

            f['msgs'][curr_idx:curr_idx + len(msgs_array)] = msgs_array
            f['msg_headers'][curr_idx:curr_idx + len(msg_headers_array)] = msg_headers_array

        # flush
        f['msgs'].flush()
        f['msg_headers'].flush()

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

    :param attempts: a parameter only relevant if file is being actively written to by another process, specifies number of refreshes to try if a synchronized state between the datasets is not achieved. A value less than ``0`` busy blocks until a synchronized state is achieved. A value greater than ``0`` tries to achieve synchronization a max of ``attempts`` before throwing a ``RuntimeError``. And a value of ``0`` does not attempt to synchronize (not recommended).

    :returns: ``int`` number of messages in file

    '''
    with h5py.File(filename, 'r', swmr=True, libver='latest') as f:
        _synchronize(attempts, f['msgs'], f['msg_headers'])
        return len(f['msgs'])

def from_rawfile(filename, start=None, end=None, version=None, io_version=None, msg_headers_only=False, mask=None, attempts=1):
    '''
    Read a chunk of bytestring messages from an existing file

    :param filename: filename to read bytestrings from

    :param start: index for the start position when reading from the file (default = ``None``). If a value less than 0 is specified, index is relative to the end of the file. If ``None`` is specified, data is read from the start of the file. If a ``mask`` is specified, does nothing.

    :param end: index for the end position when reading from the file (default = ``None``). If a value less than 0 is specified, index is relative to the end of the file. If ``None`` is specified, data is read until the end of the file. If a ``mask`` is specified, does nothing.

    :param version: required version compatibility. If ``None`` specified, uses the version stored in the file metadata

    :param io_version: required io version compatibility. If ``None`` specified, does not check the ``io_version`` file metadata

    :param msg_headers_only: optional flag to only load header information and not message bytestrings (``'msgs'`` value in return dict will be ``None`` if ``msg_headers_only=True``)

    :param mask: boolean mask alternative to ``start`` and ``end`` chunk specification to indicate specific file rows to load. Boolean 1D array with length equal to ``len_rawfile(filename)``

    :param attempts: a parameter only relevant if file is being actively written to by another process, specifies number of refreshes to try if a synchronized state between the datasets is not achieved. A value less than ``0`` busy blocks until a synchronized state is achieved. A value greater than ``0`` tries to achieve synchronization a max of ``attempts`` before throwing a ``RuntimeError``. And a value of ``0`` does not attempt to synchronize (not recommended).

    :returns: ``dict`` with keys for ``'created'``, ``'modified'``, ``'version'``, and ``'io_version'`` metadata, along with ``'msgs'`` (a ``list`` of bytestring messages) and ``'msg_headers'`` (a dict with message header field name: ``list`` of message header field data, 1 per message)

    '''
    with h5py.File(filename, 'r', swmr=True, libver='latest') as f:
        # fetch metadata
        created = f['meta'].attrs['created']
        modified = f['meta'].attrs['modified']

        # check file format version is compatible
        file_version = f['meta'].attrs['version']
        version_major = file_version.split('.')[0]
        assert (version is None) or (file_version >= version and version_major == version.split('.')[0]), 'Incompatible version mismatch! file: {}, requested: {}'.format(file_version, version)
        version_minor = min(file_version.split('.')[-1], version.split('.')[-1]) if version is not None else file_version.split('.')[-1]
        version = '{}.{}'.format(version_major,version_minor)

        # check io format version is compatible
        file_io_version = f['meta'].attrs['io_version'] if 'io_version' in f['meta'].attrs.keys() else None
        io_version_major, io_version_minor = file_io_version.split('.') if file_io_version is not None else (None,None)
        assert (io_version is None) or (file_io_version is None) or (io_version_major == io_version.split('.')[0] and io_version_minor >= io_version.split('.')[-1]), 'IO version mismatch! file: {}, requested {}'.format(file_io_version,io_version)
        io_version = file_io_version

        # check to make sure that the msgs and headers dsets are synchronized
        _synchronize(attempts, f['msgs'], f['msg_headers'])

        # define chunk of data to load
        start = int(start) if start is not None else 0
        end = int(end) if end is not None else len(f['msgs'])
        mask = mask if mask is not None else slice(start,end)

        # get data from file
        msg_headers = _parse_msg_headers(f['msg_headers'][mask], version)
        msgs = _parse_msgs(f['msgs'][mask], version) if not msg_headers_only else None

        return dict(
            created=created,
            modified=modified,
            version=version,
            io_version=io_version,
            msgs=msgs,
            msg_headers=msg_headers
            )
