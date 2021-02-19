from larpix.format.pacman_msg_format import *
from larpix import Packet_v2, TimestampPacket, SyncPacket, TriggerPacket

def test_header():
    print('test_header')
    for i,msg_type in enumerate(msg_type_table):
        bs = format_header(msg_type,i)
        print(bs)
        prsd = parse_header(bs)
        assert prsd[0] == msg_type
        assert prsd[-1] == i

def test_word():
    print('test_word')
    test_data = dict(
        DATA = (1,2,b'testing!'),
        TRIG = (b'\x01',2),
        SYNC = (b'H',1,2),
        PING = (),
        WRITE = (1,2),
        READ = (1,2),
        TX = (1,b'testing!'),
        PONG = (),
        ERR = (1,b'123456789ABCDE')
        )
    for msg_type in msg_type_table:
        for word_type in word_type_table[msg_type]:
            bs = format_word(msg_type, word_type, *test_data[word_type])
            print(bs)
            prsd = parse_word(msg_type, bs)
            assert prsd[0] == word_type
            assert prsd[1:] == test_data[word_type]

def test_packets():
    packets = []
    packets.append(TimestampPacket(timestamp=1234567))
    for i in range(100):
        packets.append(Packet_v2())
        packets[-1].io_channel = i
    packets.append(SyncPacket(timestamp=123456, sync_type=b'H', clk_source=1))
    packets.append(TriggerPacket(timestamp=123456, trigger_type=b'\x01'))

    msg = format(packets, msg_type='DATA')
    print(msg)
    new_packets = parse(msg)

    assert packets[1:] == new_packets[1:]
    assert isinstance(new_packets[0], TimestampPacket)
