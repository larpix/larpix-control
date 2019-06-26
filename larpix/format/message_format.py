'''
The module contains all the message formats used by systems that interface
with larpix-control:

    - dataserver_message_encode: convert from packets to the data server messaging format
    - dataserver_message_decode: convert from data server messaging format to packets

'''
import warnings
import struct

from larpix.larpix import Packet, TimestampPacket

def dataserver_message_decode(msgs, key_generator=None, version=(1,0), **kwargs):
    '''
    Convert a list of larpix data server messages into packets. A key generator
    should be provided if packets are to be used with an ``larpix.io.IO``
    object. The data server messages provide a ``chip_id`` and ``io_chain`` for
    keys. Additional keyword arguments can be passed along to the key generator.

    '''
    packets = []
    for msg in msgs:
        major, minor = struct.unpack('BB',msg[:2])
        if (major, minor) != version:
            warnings.warn('Message version mismatch! Expected {}, received {}'.format(version, (major,minor)))
        msg_type = struct.unpack('c',msg[2:3])[0]
        if msg_type == b'T':
            timestamp = struct.unpack('L',msg[8:15] + b'\x00')[0] # only use 7-bytes
            packets.append(TimestampPacket(timestamp=timestamp))
        elif msg_type == b'D':
            io_chain = struct.unpack('B',msg[3:4])[0]
            payload = msg[8:]
            if len(payload)%8 == 0:
                for start_index in range(0, len(payload), 8):
                    packet_bytes = payload[start_index:start_index+7]
                    packets.append(Packet(packet_bytes))
                    if key_generator:
                        packets[-1].chip_key = key_generator(chip_id=packets[-1].chipid, io_chain=io_chain, **kwargs)
        elif msg_type == b'H':
            print('Heartbeat message: {}'.format(msg[3:]))
    return packets

def dataserver_message_encode(packets, key_parser=None, version=(1,0)):
    '''
    Convert a list of packets to larpix dataserver messages. A key parser must extract
    the ``'io_chain'`` from the packet chip key. If none is provided, io_chain
    will be 0 for all packets.

    DAQ board messages are formatted using 8-byte words

        All messages:
         - byte[0] = major version
         - byte[1] = minor version
         - byte[2] = message type

            - ``b'D'``: LArPix data
            - ``b'T'``: Timestamp data
            - ``b'H'``: Heartbeat

        LArPix heartbeat messages:
         - byte[3] = ``b'H'``
         - byte[4] = ``b'B'``
         - byte[5:7] are unused

        LArPix data messages:
         - byte[3] = io channel
         - bytes[4:7] are unused
         - bytes[8:] = raw LArPix 7-byte UART words ending in a single null byte

        Timestamp data messages:
         - byte[3:7] are unused
         - byte[8:14] = 7-byte Unix timestamp
         - byte[15] is unused

    '''
    data_header_fmt='BBcBI'
    timestamp_header_fmt='BBcBI'
    msgs = []
    for packet in packets:
        msg = b''
        if isinstance(packet, Packet):
            header = [0]*len(data_header_fmt)
            header[0:2] = version[0:2]
            header[2] = b'D'
            if key_parser:
                header[3] = key_parser(packet.chip_key)['io_chain']
            msg = struct.pack(data_header_fmt, *header)
            msg += packet.bytes() + struct.pack('B',0)
        elif isinstance(packet, TimestampPacket):
            header = [0]*len(timestamp_header_fmt)
            header[0:2] = version[0:2]
            header[2] = b'T'
            msg = struct.pack(data_header_fmt, *header)
            msg += packet.bytes() + b'\x00'
        msgs += [msg]
    return msgs
