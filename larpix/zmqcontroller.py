import time
import zmq
from .larpix import Packet

class ZMQ_IO(object):
    def __init__(self, address):
        self.context = zmq.Context()
        self.sender = self.context.socket(zmq.REQ)
        self.receiver = self.context.socket(zmq.SUB)
        send_address = address + ':5555'
        receive_address = address + ':5556'
        self.sender.connect(send_address)
        self.receiver.connect(receive_address)
        self.sender_replies = []
        self.is_listening = False
        self.poller = zmq.Poller()
        self.poller.register(self.receiver, zmq.POLLIN)

    def send(self, packets):
        self.sender_replies = []
        for packet in packets:
            tosend = b'SNDWORD 0x00%s 0' % packet.bytes()[::-1].hex().encode()
            self.sender.send(tosend)
            self.sender_replies.append(self.sender.recv())

    def start_listening(self):
        if self.is_listening:
            raise RuntimeError('Already listening')
        self.receiver.setsockopt(zmq.SUBSCRIBE, b'')

    def stop_listening(self):
        if not self.is_listening:
            raise RuntimeError('Already not listening')
        self.receiver.setsockopt(zmq.UNSUBSCRIBE, b'')

    def empty_queue(self):
        packets = []
        while self.poller.poll(0):
            message = self.receiver.recv()
            if len(m) % 8 == 0:
                for start_index in range(0, len(m), 8):
                    packet_bytes = message[start_index:start_index+7]
                    packets.append(Packet(packet_bytes))
        return packets

