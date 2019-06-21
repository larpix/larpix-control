'''
The module contains all the message formats used by systems that interface
with larpix-control:

    - dataserver_message_encode: convert from packets to the data server messaging format
    - dataserver_message_decode: convert from data server messaging format to packets

'''
import warnings
from bitarray import bitarray

from larpix.larpix import Packet
import larpix.bitarrayhelper as bah

def dataserver_message_decode(msgs, key_generator=None, version=(1,0), **kwargs):
    '''
    Convert a list larpix data server messages into packets. A key generator
    should be provided if packets are to be used with an ``larpix.io.IO``
    object. The data server messages provide a ``chip_id`` and ``io_chain`` for
    keys. Additional keyword arguments can be passed along to the key generator.

    '''
    packets = []
    for msg in msgs:
        major_ba, minor_ba = bitarray(), bitarray()
        major_ba.frombytes(msg[:1])
        minor_ba.frombytes(msg[1:2])
        major, minor = [bah.touint(ba) for ba in (major_ba, minor_ba)]
        if (major, minor) != version:
            warnings.warn('Message version mismatch! Expected {}, received {}'.format(version, (major,minor)))
        msg_type = msg[2:3]
        if msg_type == b'T':
            # FIX ME: once the TimestampPacket is merged in, this need to be updated
            print('Timestamp message: {}'.format(int.from_bytes(msg[8:],byteorder='little')))
        elif msg_type == b'D':
            io_chain_ba = bitarray()
            io_chain_ba.frombytes(msg[3:4])
            io_chain = bah.touint(io_chain_ba)
            payload = msg[8:]
            if len(payload)%8 == 0:
                for start_index in range(0, len(payload), 8):
                    packet_bytes = payload[start_index:start_index+7]
                    packets.append(Packet(packet_bytes))
                    if key_generator:
                        packets[-1].chip_key = key_generator(chip_id=packets[-1].chipid, io_chain=io_chain, **kwargs)
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
         - byte[2] = message type ('D':LArPix data, 'T':Timestamp data)

        LArPix data messages:

         - byte[3] = io chain
         - bytes[4:7] are unused
         - bytes[8:] are the raw LArPix UART bytes

        Timestamp data messages:

         - byte[3:7] are unused
         - byte[8:17] 8-byte Unix timestamp

    '''
    byte_length = 8
    msgs = []
    for packet in packets:
        msg = b''
        msg += bah.fromuint(version[0], byte_length).tobytes()
        msg += bah.fromuint(version[1], byte_length).tobytes()
        if isinstance(packet, Packet):
            msg += b'D'
            if key_parser:
                msg += bah.fromuint(key_parser(packet.chip_key)['io_chain'], byte_length).tobytes()
            else:
                msg += bah.fromuint(0, byte_length).tobytes()
            msg += bah.fromuint(0, 4*byte_length).tobytes()
        else:
            msg += bah.fromuint(0, 5*byte_length).tobytes()
        msg += packet.bytes() + bah.fromuint(0, byte_length).tobytes()
        msgs += [msg]
    return msgs
