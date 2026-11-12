from collections import defaultdict
import time

import h5py
import numba
import numpy as np
import numpy.typing as npt

from .hdf5format import dtypes, init_file

DEFAULT_DIRECT_VERSION = "2.4"
BUFSIZE = 100000


def _require_direct_versions(asic_versions: dict[int, int],
                             format_version: str,
                             io_groups: npt.NDArray[np.uint8],
):
    """Validate that the ASIC versions and format version are compatible.

    Args:
        asic_versions: Mapping of io_group to ASIC version. Only versions 2
            and 3 are supported. May be a defaultdict.
        format_version: The HDF5 packet format version string (e.g. "2.4"
            or "3.0").
        io_groups: Array of IO groups for each PACMAN message.

    Raises:
        ValueError: If any ASIC version is not 2 or 3, if ASIC v3 is used
            without format version "3.0", or if ASIC v2 is used with a
            format version other than "2.4" or "3.0", or if asic_versions
            is not a defaultdict and any IO group has an unspecified version.
    """
    asic_version_list = (
        [asic_versions[0]]
        if isinstance(asic_versions, defaultdict)
        else list(asic_versions.values())
    )

    if not all(v in [2, 3] for v in asic_version_list):
        raise ValueError("Direct conversion only supports ASIC v2 and v3")

    if 3 in asic_version_list and format_version != "3.0":
        raise ValueError("ASIC v3 requires --format-version 3.0")

    if 3 not in asic_version_list and format_version not in ["2.4", "3.0"]:
        raise ValueError("ASIC v2 requires --format-version 2.4 or 3.0")

    if not isinstance(asic_versions, defaultdict):
        for iog in np.unique(io_groups):
            if iog not in asic_versions:
                raise ValueError(f"No ASIC version specified for IO group {iog}")


@numba.njit
def calc_parity(data: npt.NDArray[np.uint8]) -> np.uint8:
    """Compute the XOR parity bit of an 8-byte array.

    Packs the 8 input bytes into a 64-bit integer (big-endian) and folds
    it via successive XOR-shifts to compute the overall parity bit. This
    is a workaround for ``data.view(np.uint64)`` not being supported in
    Numba.

    Args:
        data: Array of 8 ``uint8`` values.

    Returns:
        The parity bit (0 or 1) as a ``uint8``.
    """
    # ugh the following doesn't work: x = data.view(np.uint64)[0]
    # so instead, HACK:
    x = np.uint64(
        (data[0] << 56)
        | (data[1] << 48)
        | (data[2] << 40)
        | (data[3] << 32)
        | (data[4] << 24)
        | (data[5] << 16)
        | (data[6] << 8)
        | (data[7])
    )
    x ^= x >> 32
    x ^= x >> 16
    x ^= x >> 8
    x ^= x >> 4
    x ^= x >> 2
    x ^= x >> 1
    return np.uint8(x & 1)


@numba.njit
def parse_msg_v2(
    msg: npt.NDArray[np.uint8],
    packets: npt.NDArray,
    io_group=0,
) -> int:
    """Parse a raw PACMAN message into packets using the ASIC v2 word format.

    Decodes the timestamp header word followed by a sequence of 16-byte
    data/sync/trigger words, writing the decoded fields into the given
    ``packets`` output array in place.

    Args:
        msg: Raw message bytes as an array of ``uint8``.
        packets: Output structured array (as plain ``uint8``/numeric
            columns) to be filled in place with one row per decoded
            packet. Must have at least ``nwords + 1`` rows available.
        io_group: The io_group value to stamp onto every decoded packet.

    Returns:
        The number of packets decoded from the message (``nwords + 1``).
    """
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
                trigger_type = header[1]  # sync_type
                dataword = header[2] & 0x01  # clk_source
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


@numba.njit
def parse_msg_v2_format_v3(
    msg: npt.NDArray[np.uint8],
    packets: npt.NDArray,
    io_group=0,
) -> int:
    """Parse a raw PACMAN message into v3 packets using the ASIC v2 word format.

    To conform with v3 format, remaps packet_type of data packets from 0 to 1,
    and adds (zero) reset_sample_flag and cds_flag fields.

    Decodes the timestamp header word followed by a sequence of 16-byte
    data/sync/trigger words, writing the decoded fields into the given
    ``packets`` output array in place.


    Args:
        msg: Raw message bytes as an array of ``uint8``.
        packets: Output structured array (as plain ``uint8``/numeric
            columns) to be filled in place with one row per decoded
            packet. Must have at least ``nwords + 1`` rows available.
        io_group: The io_group value to stamp onto every decoded packet.

    Returns:
        The number of packets decoded from the message (``nwords + 1``).
    """
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
        reset_sample_flag = 0
        cds_flag = 0

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
                if packet_type == 0:
                    packet_type = 1
                elif packet_type == 1:
                    packet_type = 0

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
                trigger_type = header[1]  # sync_type
                dataword = header[2] & 0x01  # clk_source
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
        packets[i][22] = reset_sample_flag
        packets[i][23] = cds_flag

    return npackets


@numba.njit
def parse_msg_v3(msg: npt.NDArray[np.uint8], packets: npt.NDArray, io_group=0) -> int:
    """Parse a raw PACMAN message into packets using the ASIC v3 word format.

    Decodes the timestamp header word followed by a sequence of 16-byte
    data/sync/trigger words, writing the decoded fields into the given
    ``packets`` output array in place. Differs from
    :func:`parse_msg_v2` in dataword width/location and the presence of
    the reset_sample_flag/cds_flag bits.

    Args:
        msg: Raw message bytes as an array of ``uint8``.
        packets: Output structured array (as plain ``uint8``/numeric
            columns) to be filled in place with one row per decoded
            packet. Must have at least ``nwords + 1`` rows available.
        io_group: The io_group value to stamp onto every decoded packet.

    Returns:
        The number of packets decoded from the message (``nwords + 1``).
    """
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
        reset_sample_flag = 0
        cds_flag = 0

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
                    | ((data[5] & 0x0F) << 24)
                )
                dataword = (np.uint16(data[6]) << 2) | (data[5] >> 6)
                trigger_type = data[7] & 0x03
                local_fifo = (data[7] >> 2) & 0x03
                shared_fifo = (data[7] >> 4) & 0x03
                downstream_marker = (data[7] >> 6) & 1
                parity = (data[7] >> 7) & 1
                # valid_parity = np.unpackbits(data).sum() % 2
                valid_parity = calc_parity(data)

                register_address = (data[1] >> 2) | ((data[2] << 6) & 0xFF)
                register_data = (data[2] >> 2) | ((data[3] << 6) & 0xFF)

                reset_sample_flag = (data[5] >> 4) & 1
                cds_flag = (data[5] >> 5) & 1

            elif wordtype == 0x53:  # 'S'
                packet_type = 6  # sync
                trigger_type = header[1]  # sync_type
                dataword = header[2] & 0x01  # clk_source
                timestamp = (
                    header[4] | (header[5] << 8) | (header[6] << 16) | (header[7] << 24)
                )

            elif wordtype == 0x54:  # 'T'
                packet_type = 7  # trigger
                trigger_type = header[1]
                timestamp = (
                    header[4] | (header[5] << 8) | (header[6] << 16) | (header[7] << 24)
                )

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
        packets[i][22] = reset_sample_flag
        packets[i][23] = cds_flag

    return npackets


def to_file_direct(
    filename: str,
    msg_list: npt.NDArray[np.uint8],
    io_groups: npt.NDArray[np.uint8],
    asic_versions: dict,
    format_version: str,
    mode="a",
):
    """Parse raw PACMAN messages directly into an HDF5 packet dataset.

    Validates the requested ASIC/format version combination, then
    iterates over ``msg_list``, dispatching each message to the
    appropriate v2 or v3 parser based on the ASIC version associated
    with its io_group, buffering decoded packets and periodically
    flushing them to the ``"packets"`` dataset in the output HDF5 file.

    Args:
        filename: Path to the HDF5 file to write to.
        msg_list: Sequence of raw PACMAN messages, each an array of
            ``uint8``.
        io_groups: Array of io_group values, one per message in
            ``msg_list``.
        asic_versions: Mapping of io_group to ASIC version (2 or 3).
        format_version: The HDF5 packet format version to write (e.g.
            "2.4" or "3.0").
        mode: File open mode passed to ``h5py.File`` (default ``"a"``,
            i.e. append/create).

    Raises:
        ValueError: If the ASIC/format version combination is invalid
            (see :func:`_require_direct_versions`), or if a message's
            io_group has no associated ASIC version.
    """
    _require_direct_versions(asic_versions, format_version, io_groups)

    dtype = dtypes[format_version]["packets"]

    with h5py.File(filename, mode) as f:
        init_file(f, format_version, chip_list=[])

        packet_dset_name = "packets"
        if packet_dset_name not in f.keys():
            packet_dset = f.create_dataset(
                packet_dset_name,
                shape=(0,),
                maxshape=(None,),
                dtype=dtype,
            )
            start_index = 0
        else:
            packet_dset = f[packet_dset_name]
            start_index = packet_dset.shape[0]

        packets = np.zeros(shape=(2 * BUFSIZE,), dtype=dtype)
        npackets = 0

        def write():
            """Flush the currently buffered packets to the HDF5 dataset."""
            nonlocal npackets
            nonlocal start_index
            packet_dset.resize(packet_dset.shape[0] + npackets, axis=0)
            packet_dset[start_index:] = packets[:npackets]
            start_index += npackets
            npackets = 0

        parse_v2 = parse_msg_v2_format_v3 if format_version == "3.0" else parse_msg_v2

        for msg, io_group in zip(msg_list, io_groups):
            parse = parse_msg_v3 if asic_versions[io_group] == 3 else parse_v2
            num_new_pkts = parse(msg, packets[npackets:], io_group)
            npackets += num_new_pkts
            if npackets > BUFSIZE:
                write()

        write()
