from larpix.larpix import Chip, Packet, TimestampPacket
from larpix.format.message_format import dataserver_message_decode, dataserver_message_encode

def test_message_format_test_packets(chip):
    expected_packets = chip.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    expected_messages = [b'\x01\x00'+b'D'+b'\x00'*5 + packet.bytes() + b'\x00' for packet in expected_packets]
    ts_packet = TimestampPacket(timestamp=123456789)
    expected_packets += [ts_packet]
    expected_messages += [b'\x01\x00'+b'T'+b'\x00'*5 + ts_packet.bytes() + b'\x00']
    print(expected_packets[-1])
    print(expected_messages[-1])
    print(dataserver_message_decode(expected_messages)[-1])
    print(expected_messages[-1])
    print(dataserver_message_encode(expected_packets)[-1])
    assert expected_messages == dataserver_message_encode(expected_packets)
    assert expected_packets == dataserver_message_decode(expected_messages)
