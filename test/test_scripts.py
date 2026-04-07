import pytest
import os
import subprocess
import sys
import os
_dir_ = os.path.dirname(os.path.abspath(__file__))

from larpix import TimestampPacket, Packet_v2, SyncPacket, TriggerPacket
import larpix.format.rawhdf5format as r_h5_fmt
import larpix.format.hdf5format as p_h5_fmt
import larpix.format.pacman_msg_format as p_msg_fmt

@pytest.fixture
def test_packets():
    pkts = []
    for _ in range(100):
        pkts += [[]]
        pkts[-1] += [TimestampPacket(0)]
        pkts[-1] += [Packet_v2(b'\x00\x00\x00\x00\x00\x00\x00\x01')] * 10
        pkts[-1] += [TriggerPacket(b'\x00', 0, 0)]
        pkts[-1] += [SyncPacket(b'\x00', 0, 0, 0)]
    return pkts

@pytest.fixture
def raw_hdf5_tmpfile(tmpdir, test_packets):
    msgs = [p_msg_fmt.format(pkts, msg_type='DATA', asic_version=2) for pkts in test_packets]
    io_groups = [0 for _ in test_packets]

    test_filename = os.path.join(tmpdir,'raw_test.h5')
    r_h5_fmt.to_rawfile(
        test_filename, msgs=msgs, msg_headers={'io_groups': io_groups}
        )
    return test_filename

@pytest.fixture
def packet_hdf5_tmpfile(tmpdir, test_packets):
    test_filename = os.path.join(tmpdir,'datalog_test.h5')
    p_h5_fmt.to_file(
        test_filename,
        packet_list=[p for pkts in test_packets for p in pkts],
        version='2.4'
        )
    return test_filename

def test_convert_rawhdf5_to_hdf5(tmpdir, raw_hdf5_tmpfile):
    out_filename = os.path.join(tmpdir, 'datalog_convert_test.h5')
    proc = subprocess.run(
        ['python', os.path.join(_dir_,'../scripts/convert_rawhdf5_to_hdf5.py'), '-i', raw_hdf5_tmpfile, '-o', out_filename, '--block_size', '10', '--asic-version', '2', '--format-version', '2.4'],
        check=True
        )

    # test read from file
    new_packets = p_h5_fmt.from_file(out_filename, version='2.4')['packets']
    raw_data = r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)
    orig_packets = [
        p_msg_fmt.parse(msg, io_group=io_group, asic_version=2)
        for io_group, msg in zip(raw_data['msg_headers']['io_groups'], raw_data['msgs'])
    ]
    assert new_packets == [p for pkts in orig_packets for p in pkts]

def test_packet_hdf5_tool(tmpdir, packet_hdf5_tmpfile, test_packets):
    out_filename = os.path.join(tmpdir, 'datalog_tool_test.h5')

    # test merge
    proc = subprocess.run(
        ['python', os.path.join(_dir_,'../scripts/packet_hdf5_tool.py'), '--merge', '-i', packet_hdf5_tmpfile, packet_hdf5_tmpfile, '-o', out_filename, '--block_size', '10'],
        check=True
        )

    # test read from file
    orig_packets = p_h5_fmt.from_file(packet_hdf5_tmpfile, version='2.4')['packets']
    orig_packets += p_h5_fmt.from_file(packet_hdf5_tmpfile, version='2.4')['packets']
    new_packets = p_h5_fmt.from_file(out_filename, version='2.4')['packets']
    assert len(orig_packets) == len(new_packets)
    assert orig_packets == new_packets

def test_raw_hdf5_tool(tmpdir, raw_hdf5_tmpfile, test_packets):
    out_filename = os.path.join(tmpdir, 'raw_tool_test.h5')

    # test merge
    proc = subprocess.run(
        ['python', os.path.join(_dir_,'../scripts/raw_hdf5_tool.py'), '--merge', '-i', raw_hdf5_tmpfile, raw_hdf5_tmpfile, '-o', out_filename, '--block_size', '10'],
        check=True
        )

    # test read data
    assert r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)['msgs'] + r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)['msgs'] == r_h5_fmt.from_rawfile(out_filename)['msgs']

    # test merge
    proc = subprocess.run(
        ['python', os.path.join(_dir_,'../scripts/raw_hdf5_tool.py'), '--split', '-i', out_filename, '-o', tmpdir, '--max_length', '0', '--block_size', '10'],
        check=True
        )

    # test read data
    assert r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)['msgs'] + r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)['msgs'] == r_h5_fmt.from_rawfile(out_filename)['msgs']

