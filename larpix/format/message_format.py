'''
The module contains all the message formats used by systems that interface
with larpix-control:

    - dataserver_message_encode: convert from packets to the data server messaging format
    - dataserver_message_decode: convert from data server messaging format to packets

'''
import warnings
import struct

from larpix.larpix import Packet, TimestampPacket, Packet_v1, Packet_v2

def dataserver_message_encode(packets, version=(1,0)):
    r'''
    Convert a list of packets to larpix dataserver messages. DAQ board messages are formatted using 8-byte words with the first word being a header word describing the interpretation of other words in the message. These messages are formatted as follows

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

    Example usage::

        from larpix.larpix import Packet, Key
        packet = Packet()
        packet.chip_key = Key('1-1-1')
        msgs = datserver_message_encode([packet])
        msgs[0] # b'\x01\x00D\x01\x00\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00'
        msgs[0][:8] # header
        msgs[0][8:] # data words

    :param packets: list of ``larpix.Packet`` objects

    :param version: optional, encode a message in specified version format, ``tuple`` of major, minor numbers

    :returns: list of bytestream messages, 1 for each packet

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
            if packet.io_channel:
                header[3] = packet.io_channel
            else:
                raise ValueError('all packets must have a declared io_channel')
            msg = struct.pack(data_header_fmt, *header)
            if isinstance(packet, Packet_v1):
                msg += packet.bytes() + struct.pack('B',0)
            elif isinstance(packet, Packet_v2):
                msg += packet.bytes()
        elif isinstance(packet, TimestampPacket):
            header = [0]*len(timestamp_header_fmt)
            header[0:2] = version[0:2]
            header[2] = b'T'
            msg = struct.pack(data_header_fmt, *header)
            msg += packet.bytes() + b'\x00'
        msgs += [msg]
    return msgs

def dataserver_message_decode(msgs, version=(1,0), **kwargs):
    r'''
    Convert a list of larpix data server messages into packets. Additional packet meta data can be passed along via kwargs E.g.::

        msg = b'\x01\x00D\x01\x00\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00'
        packets = dataserver_message_decode([msg], io_group=1)
        packets[0] # Packet(b'\x04\x00\x00\x00\x00\x00\x00'), key of '1-1-1'

    :param msgs: list of bytestream messages each starting with a single 8-byte header word, followed by N 8-byte data words

    :param version: optional, message version to validate against, ``tuple`` of major, minor version numbers

    :returns: list of ``larpix.Packet`` and ``larpix.TimestampPacket`` objects

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
            if kwargs:
                for key,value in kwargs.items():
                    setattr(packets[-1], key, value)
        elif msg_type == b'D':
            io_chain = struct.unpack('B',msg[3:4])[0]
            payload = msg[8:]
            if len(payload)%8 == 0:
                for start_index in range(0, len(payload), 8):
                    packet_bytes = payload[start_index:start_index+8]
                    if Packet == Packet_v1:
                        packets.append(Packet(packet_bytes[:-1]))
                    elif Packet == Packet_v2:
                        packets.append(Packet(packet_bytes))
                    packets[-1].io_channel = io_chain
                    if kwargs:
                        for key,value in kwargs.items():
                            setattr(packets[-1], key, value)
        elif msg_type == b'H':
            print('Heartbeat message: {}'.format(msg[3:]))
    return packets
