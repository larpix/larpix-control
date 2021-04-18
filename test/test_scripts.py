import pytest
import os
import subprocess
import sys

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
    msgs = [p_msg_fmt.format([pkts]) for pkts in test_packets]
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
        packet_list=[p for pkts in test_packets for p in pkts]
        )
    return test_filename

def test_convert_rawhdf5_to_hdf5(tmpdir, raw_hdf5_tmpfile):
    out_filename = os.path.join(tmpdir, 'datalog_convert_test.h5')
    proc = subprocess.run(
        ['convert_rawhdf5_to_hdf5.py', '-i', raw_hdf5_tmpfile, '-o', out_filename, '--block_size', '10']
        )
    out = proc.stdout.decode('utf-8') + '\n' + proc.stderr.decode('utf-8') if sys.version_info[1] == 6 else None
    assert proc.returncode == 0, \
        f'Return code: {proc.returncode}\nout: {out}'

    # test read from file
    new_packets = p_h5_fmt.from_file(out_filename)['packets']
    orig_packets = [p_msg_fmt.parse(msg) for msg in r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)['msgs']]
    assert new_packets == [p for pkts in orig_packets for p in pkts], \
        f'Return code: {proc.returncode}\nout: {out}'

def test_packet_hdf5_tool(tmpdir, packet_hdf5_tmpfile, test_packets):
    out_filename = os.path.join(tmpdir, 'datalog_tool_test.h5')

    # test merge
    proc = subprocess.run(
        ['packet_hdf5_tool.py', '--merge', '-i', packet_hdf5_tmpfile, packet_hdf5_tmpfile, '-o', out_filename, '--block_size', '10']
        )
    out = proc.stdout.decode('utf-8') + '\n' + proc.stderr.decode('utf-8') if sys.version_info[1] == 6 else None
    assert proc.returncode == 0, \
        f'Return code: {proc.returncode}\nout: {out}'

    # test read from file
    orig_packets = p_h5_fmt.from_file(packet_hdf5_tmpfile)['packets']
    orig_packets += p_h5_fmt.from_file(packet_hdf5_tmpfile)['packets']
    new_packets = p_h5_fmt.from_file(out_filename)['packets']
    assert len(orig_packets) == len(new_packets)
    assert orig_packets == new_packets, \
        f'Return code: {proc.returncode}\nout: {out}'

def test_raw_hdf5_tool(tmpdir, raw_hdf5_tmpfile, test_packets):
    out_filename = os.path.join(tmpdir, 'raw_tool_test.h5')

    # test merge
    proc = subprocess.run(
        ['raw_hdf5_tool.py', '--merge', '-i', raw_hdf5_tmpfile, raw_hdf5_tmpfile, '-o', out_filename, '--block_size', '10']
        )
    out = proc.stdout.decode('utf-8') + '\n' + proc.stderr.decode('utf-8') if sys.version_info[1] == 6 else None
    assert proc.returncode == 0, \
        f'Return code: {proc.returncode}\nout: {out}'

    # test read data
    assert r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)['msgs'] + r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)['msgs'] == r_h5_fmt.from_rawfile(out_filename)['msgs']

    # test merge
    proc = subprocess.run(
        ['raw_hdf5_tool.py', '--split', '-i', out_filename, '-o', tmpdir, '--max_length', '0', '--block_size', '10']
        )
    out = proc.stdout.decode('utf-8') + '\n' + proc.stderr.decode('utf-8') if sys.version_info[1] == 6 else None
    assert proc.returncode == 0, \
        f'Return code: {proc.returncode}\nout: {out}'

    # test read data
    assert r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)['msgs'] + r_h5_fmt.from_rawfile(raw_hdf5_tmpfile)['msgs'] == r_h5_fmt.from_rawfile(out_filename)['msgs']

