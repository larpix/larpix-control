from __future__ import print_function

import pytest
import h5py
import numpy as np

from larpix.format.rawhdf5format import (to_rawfile, from_rawfile, len_rawfile)

@pytest.fixture
def tmpfile(tmpdir):
    return str(tmpdir.join('test_raw.h5'))

@pytest.fixture
def testdata():
    test_msgs = [
        b'\x00'*8+b'\x01'*16,
        b'\x01'*8+b'\x02'*16,
        b'\x02'*8+b'\x03'*16
        ]
    test_io_groups = [
        0,
        1,
        2
    ]
    return test_io_groups, test_msgs

def test_incompatible_version_v0_0(tmpfile):
    to_rawfile(tmpfile, version='0.0', io_version='0.0')
    assert from_rawfile(tmpfile, version='0.0')['io_version'] == '0.0'
    with pytest.raises(AssertionError):
        from_rawfile(tmpfile, version='1.0')
        pytest.fail('Should identify incompatible version')
    with pytest.raises(AssertionError):
        from_rawfile(tmpfile, version='0.1')
        pytest.fail('Should identify incompatible version')
    with pytest.raises(AssertionError):
        to_rawfile(tmpfile, io_version='0.1')
        pytest.fail('Should complain about incompatible io version')
    with pytest.raises(AssertionError):
        to_rawfile(tmpfile, io_version='1.0')
        pytest.fail('Should complain about incompatible io version')
    with pytest.raises(AssertionError):
        from_rawfile(tmpfile, io_version='0.1')
        pytest.fail('Should complain about incompatible io version')
    with pytest.raises(AssertionError):
        from_rawfile(tmpfile, io_version='1.0')
        pytest.fail('Should complain about incompatible io version')

def test_file_empty_v0_0(tmpfile):
    to_rawfile(tmpfile, version='0.0')
    assert len_rawfile(tmpfile) == 0

def test_file_full_v0_0(tmpfile, testdata):
    io_groups, msgs = testdata
    to_rawfile(tmpfile, msgs=msgs, msg_headers={'io_groups':io_groups}, version='0.0')
    assert len_rawfile(tmpfile) == len(msgs)

    rd = from_rawfile(tmpfile)
    assert len(rd['msgs']) == len(msgs)
    assert rd['msgs'][0] == msgs[0]
    assert rd['msgs'][-1] == msgs[-1]
    assert set(rd['msgs']) == set(msgs)
    assert len(rd['msg_headers']['io_groups']) == len(io_groups)
    assert rd['msg_headers']['io_groups'][0] == io_groups[0]
    assert rd['msg_headers']['io_groups'][-1] == io_groups[-1]
    assert set(rd['msg_headers']['io_groups']) == set(io_groups)

def test_file_partial_read_v0_0(tmpfile, testdata):
    io_groups, msgs = testdata
    to_rawfile(tmpfile, msgs=msgs, msg_headers={'io_groups':io_groups}, version='0.0')

    # skip reading msgs
    rd = from_rawfile(tmpfile, msg_headers_only=True)
    assert rd['msgs'] is None
    assert len(rd['msg_headers']['io_groups']) == 3

    # read from end
    rd = from_rawfile(tmpfile, start=-1)
    assert len(rd['msgs']) == 1
    assert rd['msgs'][0] == msgs[-1]
    assert len(rd['msg_headers']['io_groups']) == 1
    assert rd['msg_headers']['io_groups'][0] == io_groups[-1]

    # read from middle
    rd = from_rawfile(tmpfile, start=1, end=3)
    assert len(rd['msgs']) == 2
    assert rd['msgs'][0] == msgs[1]
    assert len(rd['msg_headers']['io_groups']) == 2
    assert rd['msg_headers']['io_groups'][0] == io_groups[1]

    # read with mask
    rd = from_rawfile(tmpfile, mask=np.array([0,1,0]).astype(bool))
    assert len(rd['msgs']) == 1
    assert rd['msgs'][0] == msgs[1]
    assert len(rd['msg_headers']['io_groups']) == 1
    assert rd['msg_headers']['io_groups'][0] == io_groups[1]

def test_file_append_v0_0(tmpfile, testdata):
    io_groups, msgs = testdata
    to_rawfile(tmpfile, msgs=msgs, msg_headers={'io_groups':io_groups}, version='0.0')
    to_rawfile(tmpfile, msgs=msgs[0:1], msg_headers={'io_groups':io_groups[0:1]}, version='0.0')
    assert len_rawfile(tmpfile) == len(msgs)+1

    rd = from_rawfile(tmpfile)
    assert len(rd['msgs']) == len(msgs)+1
    assert rd['msgs'][0] == msgs[0]
    assert rd['msgs'][-1] == msgs[0]
    assert set(rd['msgs']) == set(msgs)
    assert len(rd['msg_headers']['io_groups']) == len(io_groups)+1
    assert rd['msg_headers']['io_groups'][0] == io_groups[0]
    assert rd['msg_headers']['io_groups'][-1] == io_groups[0]
    assert set(rd['msg_headers']['io_groups']) == set(io_groups)


