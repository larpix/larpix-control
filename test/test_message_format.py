from larpix.larpix import Chip, Packet
from larpix.format.message_format import dataserver_message_decode, dataserver_message_encode

def test_message_format_test_packets():
    c = Chip(5,'1-5')
    expected_packets = c.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    expected_messages = [bytes([1,0])+b'D'+bytes([0,0,0,0,0]) + packet.bytes() + bytes(1) for packet in expected_packets]
    assert expected_messages == dataserver_message_encode(expected_packets)
    assert expected_packets == dataserver_message_decode(expected_messages)
