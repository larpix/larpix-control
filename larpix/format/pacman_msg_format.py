'''
A python interface to the pacman ZMQ message format.

The pacman ZMQ messages are a raw bytestring with two components: a short
header and N words. It's a bit cumbersome to work with bytestrings in data (and
keep track of endianness / etc), so this module allows you to translate between
native python objects and the pacman message bytestring.

Access to the message content is provided by the `parse_msg(msg)` method which
takes a single pacman message bytestring as an argument, e.g.::

    msg = b'!-----\x01\x00P---------------' # a simple ping response
    data = parse_msg(msg) # (('REP',123456,1), [('PONG')])
    msg = b'D-----\x01\x00D\x01------datadata' # a simple data message
    data = parse_msg(msg) # (('DATA',123456,1), [('DATA',1,1234,b'datadata')])

The creation of messages can be performed with the inverse method,
`format_msg(msg_type, msg_words)`. Here, the `msg_type` is one of `'DATA'`,
`'REQ'`, or `'REP'`, and `msg_words` is a `list` of tuples indicating the word
type (index 0) and the word data (index 1, 2, ...). Word types are specified
by strings that can be found in the `word_type_table`. The necessary fields
(and primitive types) for the word data is described in the `word_fmt_table`.
E.g.::

    data = ('REP', [('PONG')]) # simple ping response
    msg = format_msg(*data) # b'!----\x00\x01\x00P\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    data = ('DATA', [('DATA',1,1234,b'datadata')])
    msg = format_msg(*data) # b'D----\x00\x01\x00D\x01\x00\x00\x00\x00\x00\x00datadata'

To facilitate translating to/from larpix control packet objects, you can use
the `format(pkts, msg_type)` and `parse(msg, io_group=None)` methods. E.g.::

    packet = Packet()
    packet.io_channel = 1
    msg = format([packet]) # b'?----\x00\x01\x00D\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    packets = parse(msg, io_group=1) # [Packet(b'\x00\x00\x00\x00\x00\x00\x00\x00')]
    packets[0].io_group # 1

Note that no `io_group` data is contained within a pacman message. This means
that when formatting messages, packets' `io_group` field is ignored. And when
parsing messages, an `io_group` value needs to be specified at the time of
parsing.

'''
import struct
from bidict import bidict
import time

from larpix import Packet_v2

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
    DATA='<cB2xL8s',
    TRIG='<cHxL8x',
    SYNC='<cBxxL8x',
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
    return msg_header_struct.pack(
        msg_type_table[msg_type],
        int(time.time()),
        msg_words
        )

def format_word(msg_type, word_type, *data):
    return word_struct_table[word_type].pack(
        word_type_table[msg_type][word_type],
        *data
        )

def parse_header(msg):
    '''
    Returns a tuple of the data contained in the header:
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
    msg_data should be a list of tuples that can be passed into format_word

    '''
    bytestream = format_header(msg_type, len(msg_words))
    for msg_word in msg_words:
        bytestream += format_word(msg_type, *msg_word)
    return bytestream

def parse_msg(msg):
    '''
    returns a tuple of (<header data>, [<word 0 data>, ...])

    '''
    header = parse_header(msg)
    words = list()
    for idx in range(HEADER_LEN,len(msg),WORD_LEN):
        words.append(parse_word(
            header[0],
            msg[idx:idx+WORD_LEN]
            ))
    return header, words

def _packet_data_tx(pkt, *args):
    return (pkt.io_channel, pkt.bytes())

def _packet_data_data(pkt, ts_pacman, *args):
    (pkt.io_channel, ts_pacman, pkt.bytes())

def format(packets, msg_type='REQ', ts_pacman=0):
    '''
    Converts larpix packets into a single PACMAN message

    '''
    word_type = 'TX'
    get_data = _packet_data_tx

    if msg_type == 'DATA':
        word_type = 'DATA'
        get_data = _packet_data_data

    word_datas = list()
    for packet in packets:
        word_data = [word_type]
        word_data += get_data(packet, ts_pacman)
        word_datas.append(word_data)
    return format_msg(msg_type, word_datas)

def parse(msg, io_group=None):
    '''
    Converts a PACMAN message into larpix packets (ignoring non-data packets)

    '''
    packets = list()
    header, word_datas = parse_msg(msg)
    for word_data in word_datas:
        if word_data[0] in ('TX', 'DATA'):
            packet = Packet_v2(word_data[-1])
            packet.io_group = io_group
            packet.io_channel = word_data[1]
            packets.append(packet)
    return packets






