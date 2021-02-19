'''
A python interface to the pacman ZMQ message format.

The pacman ZMQ messages are a raw bytestring with two components: a short
header and N words. It's a bit cumbersome to work with bytestrings in data (and
keep track of endianness / etc), so this module allows you to translate between
native python objects and the pacman message bytestring.

To import this module::

    import larpix.format.pacman_msg_format as pacman_msg_fmt

Access to the message content is provided by the ``parse_msg(msg)`` method which
takes a single pacman message bytestring as an argument, e.g.::

    msg = b'!-----\x01\x00P---------------' # a simple ping response
    data = pacman_msg_fmt.parse_msg(msg) # (('REP',123456,1), [('PONG')])
    msg = b'D-----\x01\x00D\x01------datadata' # a simple data message
    data = pacman_msg_fmt.parse_msg(msg) # (('DATA',123456,1), [('DATA',1,1234,b'datadata')])

The creation of messages can be performed with the inverse method,
``format_msg(msg_type, msg_words)``. Here, the ``msg_type`` is one of ``'DATA'``,
``'REQ'``, or ``'REP'``, and ``msg_words`` is a ``list`` of tuples indicating the word
type (index 0) and the word data (index 1, 2, ...). Word types are specified
by strings that can be found in the ``word_type_table``. The necessary fields
(and primitive types) for the word data is described in the ``word_fmt_table``.
E.g.::

    data = ('REP', [('PONG')]) # simple ping response
    msg = pacman_msg_fmt.format_msg(*data) # b'!----\x00\x01\x00P\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    data = ('DATA', [('DATA',1,1234,b'datadata')])
    msg = pacman_msg_fmt.format_msg(*data) # b'D----\x00\x01\x00D\x01\x00\x00\x00\x00\x00\x00datadata'

To facilitate translating to/from ``larpix-control`` packet objects, you can use
the ``format(pkts, msg_type)`` and ``parse(msg, io_group=None)`` methods. E.g.::

    packet = Packet_v2()
    packet.io_channel = 1
    msg = pacman_msg_fmt.format([packet]) # b'?----\x00\x01\x00D\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    packets = pacman_msg_fmt.parse(msg, io_group=1) # [Packet_v2(b'\x00\x00\x00\x00\x00\x00\x00\x00')]
    packets[0].io_group # 1

Note that no ``io_group`` data is contained within a pacman message. This means
that when formatting messages, packets' ``io_group`` field is ignored, and when
parsing messages, an ``io_group`` value needs to be specified at the time of
parsing.

'''
import struct
from bidict import bidict
import time

from larpix import Packet_v2, TriggerPacket, SyncPacket, TimestampPacket

#: Most up-to-date message format version.
latest_version = '0.0'

HEADER_LEN=8
WORD_LEN=16
MSG_TYPE_DATA=b'D'
MSG_TYPE_REQ=b'?'
MSG_TYPE_REP=b'!'
WORD_TYPE_DATA=b'D'
WORD_TYPE_TRIG=b'T'
WORD_TYPE_SYNC=b'S'
WORD_TYPE_PING=b'P'
WORD_TYPE_WRITE=b'W'
WORD_TYPE_READ=b'R'
WORD_TYPE_TX=WORD_TYPE_DATA
WORD_TYPE_PONG=WORD_TYPE_PING
WORD_TYPE_ERR=b'E'

msg_type_table = bidict([
    ('REQ',MSG_TYPE_REQ),
    ('REP',MSG_TYPE_REP),
    ('DATA',MSG_TYPE_DATA)
    ])
word_type_table = dict(
    REQ=bidict([
        ('PING',WORD_TYPE_PING),
        ('WRITE',WORD_TYPE_WRITE),
        ('READ',WORD_TYPE_READ),
        ('TX',WORD_TYPE_TX)
        ]),
    REP=bidict([
        ('WRITE',WORD_TYPE_WRITE),
        ('READ',WORD_TYPE_READ),
        ('TX',WORD_TYPE_TX),
        ('PONG',WORD_TYPE_PONG),
        ('ERR',WORD_TYPE_ERR)
        ]),
    DATA=bidict([
        ('DATA',WORD_TYPE_DATA),
        ('TRIG',WORD_TYPE_TRIG),
        ('SYNC',WORD_TYPE_SYNC)
        ])
    )

msg_header_fmt = '<cLxH'
msg_header_struct = struct.Struct(msg_header_fmt)

word_fmt_table = dict(
    DATA='<cBLxx8s',
    TRIG='<2cxxL8x',
    SYNC='<2cBxL8x',
    PING='<c15x',
    WRITE='<c3xL4xL',
    READ='<c3xL4xL',
    TX='<cB6x8s',
    PONG='<c15x',
    ERR='<cB14s'
    )
word_struct_table = dict([
    (word_type, struct.Struct(word_fmt))
    for word_type, word_fmt in word_fmt_table.items()
    ])

def format_header(msg_type, msg_words):
    '''
    Generates a header-formatted bytestring of
    message type ``msg_type`` and with ``msg_words``
    specified words

    '''
    return msg_header_struct.pack(
        msg_type_table[msg_type],
        int(time.time()),
        msg_words
        )

def format_word(msg_type, word_type, *data):
    '''
    Generates a word-formatted bytestring of
    word type specified by the ``msg_type`` and
    ``word_type``. The data contained within the word
    should be passed in as additional positional arguments
    in the order that they appear in the word (least significant byte first). E.g. for a data word::

        data_word = format_word('DATA','DATA',<io_channel>,<receipt_timestamp>,<data_word_content>)

    '''
    return word_struct_table[word_type].pack(
        word_type_table[msg_type][word_type],
        *data
        )

def parse_header(msg):
    '''
    Returns a tuple of the data contained in the header::

        (<msg type>, <msg time>, <msg words>)

    '''
    msg_header_data = msg_header_struct.unpack(msg[:HEADER_LEN])
    return (msg_type_table.inv[msg_header_data[0]],) + tuple(msg_header_data[1:])

def parse_word(msg_type, word):
    '''
    Returns a tuple of data contained in word (little endian),
    first item is always the word type

    '''
    word_type = word_type_table[msg_type].inv[word[0:1]]
    return (word_type,) + tuple(word_struct_table[word_type].unpack(word)[1:])

def format_msg(msg_type, msg_words):
    '''
    ``msg_words`` should be a list of tuples that can be unpacked and passed into ``format_word``

    '''
    bytestream = format_header(msg_type, len(msg_words))
    for msg_word in msg_words:
        bytestream += format_word(msg_type, *msg_word)
    return bytestream

def parse_msg(msg):
    '''
    returns a tuple of::

        (<header data>, [<word 0 data>, ...])

    '''
    header = parse_header(msg)
    words = list()
    for idx in range(HEADER_LEN,len(msg),WORD_LEN):
        words.append(parse_word(
            header[0],
            msg[idx:idx+WORD_LEN]
            ))
    return header, words

def _replace_none(obj, attr, default=0):
    return getattr(obj, attr) if getattr(obj, attr) is not None else default

def _packet_data_req(pkt, *args):
    if isinstance(pkt, Packet_v2):
        return ('TX',
                _replace_none(pkt,'io_channel'),
                pkt.bytes())
    return tuple()

def _packet_data_data(pkt, ts_pacman, *args):
    if isinstance(pkt, Packet_v2):
        return ('DATA',
                _replace_none(pkt,'io_channel'),
                pkt.receipt_timestamp if hasattr(pkt,'receipt_timestamp') else ts_pacman,
                pkt.bytes())
    elif isinstance(pkt, SyncPacket):
        return ('SYNC',
                _replace_none(pkt,'sync_type'),
                _replace_none(pkt,'clk_source'),
                _replace_none(pkt,'timestamp'))
    elif isinstance(pkt, TriggerPacket):
        return ('TRIG',
                _replace_none(pkt,'trigger_type'),
                _replace_none(pkt,'timestamp'))
    return tuple()

def format(packets, msg_type='REQ', ts_pacman=0):
    '''
    Converts larpix packets into a single PACMAN message.
    The message header is automatically generated.

    Note:: For request messages, this method only formats ``Packet_v2`` objects. For data messages, this method only formats ``Packet_v2``, ``SyncPacket``, and ``TriggerPacket`` objects.

    '''
    get_data = _packet_data_req
    if msg_type == 'DATA':
        get_data = _packet_data_data

    word_datas = list()
    for packet in packets:
        word_data = get_data(packet, ts_pacman)
        if len(word_data) == 0: continue
        word_datas.append(word_data)
    return format_msg(msg_type, word_datas)

def parse(msg, io_group=None):
    '''
    Converts a PACMAN message into larpix packets

    The header is parsed into a ``TimestampPacket``,
    data words are parsed into ``Packet_v2`` objects,
    trigger words are parsed into ``TriggerPacket`` objects,
    and sync words are parsed into ``SyncPacket`` objects.

    '''
    packets = list()
    header, word_datas = parse_msg(msg)
    packets.append(TimestampPacket(timestamp=header[1]))
    packets[0].io_group = io_group
    for word_data in word_datas:
        packet = None
        if word_data[0] in ('TX', 'DATA'):
            packet = Packet_v2(word_data[-1])
            packet.receipt_timestamp = word_data[2]
            packet.io_group = io_group
            packet.io_channel = word_data[1]
        elif word_data[0] == 'TRIG':
            packet = TriggerPacket(trigger_type=word_data[1], timestamp=word_data[2])
            packet.io_group = io_group
        elif word_data[0] == 'SYNC':
            packet = SyncPacket(sync_type=word_data[1], clk_source=word_data[2] & 0x01, timestamp=word_data[3])
            packet.io_group = io_group
        if packet is not None:
            packets.append(packet)
    return packets






