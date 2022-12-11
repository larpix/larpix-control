import time

import h5py
import numba
import numpy as np

from .hdf5format import dtypes, init_file

VERSION = "2.4"
DTYPE = dtypes[VERSION]["packets"]
BUFSIZE = 100000


@numba.njit
def calc_parity(data: np.array):
    "data is an array of 8 uint8s"
    # ugh the following doesn't work: x = data.view(np.uint64)[0]
    # so instead, HACK:
    x = np.uint64((data[0] << 56) | (data[1] << 48) | (data[2] << 40) | (data[3] << 32) |
                  (data[4] << 24) | (data[5] << 16) | (data[6] << 8)  | (data[7]))
    x ^= x >> 32
    x ^= x >> 16
    x ^= x >> 8
    x ^= x >> 4
    x ^= x >> 2
    x ^= x >> 1
    return x & 1


@numba.njit
def parse_msg(msg: np.array, packets: np.array, io_group=0) -> int:
    "packets is output parameter. array types are uint8"
    # assert msg[0] == ord("D")
    pacman_timestamp = msg[1] | (msg[2] << 8) | (msg[3] << 16) | (msg[4] << 24)
    nwords = msg[6] | (msg[7] << 8)

    npackets = nwords + 1

    for i in range(npackets):
        io_channel = 0
        chip_id = 0
        packet_type = 0
        downstream_marker = 0
        parity = 0
        valid_parity = 0
        channel_id = 0
        timestamp = 0
        dataword = 0
        trigger_type = 0
        local_fifo = 0
        shared_fifo = 0
        register_address = 0
        register_data = 0
        direction = 0
        local_fifo_events = 0
        shared_fifo_events = 0
        counter = 0
        fifo_diagnostics_enabled = 0
        first_packet = 0
        receipt_timestamp = 0

        if i == 0:
            packet_type = 4  # timestamp
            timestamp = pacman_timestamp
        else:
            wordstart = 8 + (16 * (i - 1))
            word = msg[wordstart : (wordstart + 16)]
            header, data = word[:8], word[8:]

            wordtype = header[0]

            if wordtype == 0x44:  # 'D'
                packet_type = data[0] & 3
                io_channel = header[1]
                receipt_timestamp = (
                    header[2] | (header[3] << 8) | (header[4] << 16) | (header[5] << 24)
                )
                chip_id = (data[0] >> 2) | ((data[1] << 6) & 0xFF)
                channel_id = data[1] >> 2
                timestamp = (
                    data[2]
                    | (data[3] << 8)
                    | (data[4] << 16)
                    | ((data[5] & 0x7F) << 24)
                )
                first_packet = (data[5] >> 7) & 1
                dataword = data[6]
                trigger_type = data[7] & 0x03
                local_fifo = (data[7] >> 2) & 0x03
                shared_fifo = (data[7] >> 4) & 0x03
                downstream_marker = (data[7] >> 6) & 1
                parity = (data[7] >> 7) & 1
                # valid_parity = np.unpackbits(data).sum() % 2
                valid_parity = calc_parity(data)

                register_address = (data[1] >> 2) | ((data[2] << 6) & 0xFF)
                register_data = (data[2] >> 2) | ((data[3] << 6) & 0xFF)

            elif wordtype == 0x53:  # 'S'
                packet_type = 6  # sync
                trigger_type = sync_type = header[1]
                dataword = clk_source = header[2] & 0x01
                timestamp = (
                    header[4] | (header[5] << 8) | (header[6] << 16) | (header[7] << 24)
                )

            elif wordtype == 0x54:  # 'T'
                packet_type = 7  # trigger
                trigger_type = header[1]
                timestamp = (
                    header[4] | (header[5] << 8) | (header[6] << 16) | (header[7] << 24)
                )

        # NOTE: The following methods don't seem to work in Numba:
        # packets[i] = ( io_group, io_channel, ... )
        # packets[i] = ( np.uint8(io_group), np.uint8(io_channel), ... )

        # ...so instead we painfully write the indices
        packets[i][0] = io_group
        packets[i][1] = io_channel
        packets[i][2] = chip_id
        packets[i][3] = packet_type
        packets[i][4] = downstream_marker
        packets[i][5] = parity
        packets[i][6] = valid_parity
        packets[i][7] = channel_id
        packets[i][8] = timestamp
        packets[i][9] = dataword
        packets[i][10] = trigger_type
        packets[i][11] = local_fifo
        packets[i][12] = shared_fifo
        packets[i][13] = register_address
        packets[i][14] = register_data
        packets[i][15] = direction
        packets[i][16] = local_fifo_events
        packets[i][17] = shared_fifo_events
        packets[i][18] = counter
        packets[i][19] = fifo_diagnostics_enabled
        packets[i][20] = first_packet
        packets[i][21] = receipt_timestamp

    return npackets


def to_file_direct(filename, msg_list=[], io_groups=[], chip_list=[], mode="a"):
    with h5py.File(filename, mode) as f:
        init_file(f, VERSION, chip_list)

        packet_dset_name = "packets"
        if packet_dset_name not in f.keys():
            packet_dset = f.create_dataset(
                packet_dset_name,
                shape=(0,),
                maxshape=(None,),
                dtype=DTYPE,
            )
            start_index = 0
        else:
            packet_dset = f[packet_dset_name]
            start_index = packet_dset.shape[0]

        packets = np.zeros(shape=(2*BUFSIZE,), dtype=DTYPE)
        npackets = 0

        def write():
            nonlocal npackets
            nonlocal start_index
            packet_dset.resize(packet_dset.shape[0] + npackets, axis=0)
            packet_dset[start_index:] = packets[:npackets]
            start_index += npackets
            npackets = 0

        for msg, io_group in zip(msg_list, io_groups):
            num_new_pkts = parse_msg(msg, packets[npackets:], io_group)
            npackets += num_new_pkts
            if npackets > BUFSIZE:
                write()

        write()
