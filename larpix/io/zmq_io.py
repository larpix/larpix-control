import time
import zmq

from larpix.larpix import Packet

class ZMQ_IO(object):
    '''
    The ZMQ_IO object interfaces with the Bern LArPix v2 module using
    the ZeroMQ communications protocol.

    This object handles the required communications, and also has extra
    methods for additional functionality, including system reset, packet
    count, clock frequency, and more.

    '''
    _logger = None

    def __init__(self, address):
        self.context = zmq.Context()
        self.sender = self.context.socket(zmq.REQ)
        self.receiver = self.context.socket(zmq.SUB)
        self.hwm = 20000
        self.receiver.set_hwm(self.hwm)
        send_address = address + ':5555'
        receive_address = address + ':5556'
        self.sender.connect(send_address)
        self.receiver.connect(receive_address)
        self.sender_replies = []
        self.is_listening = False
        self.poller = zmq.Poller()
        self.poller.register(self.receiver, zmq.POLLIN)
        self.logger = None
        if not (self._logger is None):
            self.logger = self._logger

    def send(self, packets):
        self.sender_replies = []
        send_time = time.time()
        msg_datas = self.encode(packets)
        for msg_data in msg_datas:
            tosend = b'SNDWORD ' + msg_data
            self.sender.send(tosend)
            self.sender_replies.append(self.sender.recv())

            if self.logger:
                self.logger.record({'data_type':'write','data':msg_data,'time':send_time})

    def start_listening(self):
        if self.is_listening:
            raise RuntimeError('Already listening')
        self.is_listening = True
        self.receiver.setsockopt(zmq.SUBSCRIBE, b'')

    def stop_listening(self):
        if not self.is_listening:
            raise RuntimeError('Already not listening')
        self.is_listening = False
        self.receiver.setsockopt(zmq.UNSUBSCRIBE, b'')

    @staticmethod
    def decode(msgs):
        '''
        Convert a list ZMQ messages into packets
        '''
        packets = []
        for msg in msgs:
            if len(msg) % 8 == 0:
                for start_index in range(0, len(msg), 8):
                    packet_bytes = msg[start_index:start_index+7]
                    packets.append(Packet(packet_bytes))
        return packets

    @staticmethod
    def encode(packets):
        '''
        Encode a list of packets into ZMQ messages
        '''
        msg_data = [b'0x00%s 0' % packet.bytes()[::-1].hex().encode() for packet in packets]
        return msg_data

    def empty_queue(self):
        packets = []
        bytestream_list = []
        bytestream = b''
        n_recv = 0
        read_time = time.time()
        while self.poller.poll(0) and n_recv < self.hwm:
            message = self.receiver.recv()
            n_recv += 1
            bytestream_list.append(message)
            packets += self.decode([message])
        #print('len(bytestream_list) = %d' % len(bytestream_list))
        bytestream = b''.join(bytestream_list)
        if self.logger:
            for msg in bytestream_list:
                self.logger.record({'data_type':'read','data':msg,'time':read_time})
        return packets, bytestream

    def reset(self):
        '''
        Send a reset pulse to the LArPix ASICs.

        '''
        self.sender.send(b'SYRESET')
        return self.sender.recv()

    def set_clock(self, freq_khz):
        '''
        Set the LArPix CLK2X freqency (in kHz).

        '''
        self.sender.send(b'SETFREQ %s' % hex(freq_khz).encode())
        return self.sender.recv()

    def set_testpulse_freq(self, divisor):
        '''
        Set the testpulse frequency, computed by dividing the CLK2X
        frequency by ``divisor``.

        '''
        self.sender.send(b'SETFTST %s' % hex(divisor).encode())
        return self.sender.recv()

    def get_packet_count(self, io_channel):
        '''
        Get the number of packets received, as determined by the number
        of UART "start" bits processed.

        '''
        self.sender.send(b'GETSTAT %d' % io_channel)
        result = self.sender.recv()
        space = result.find(b' ')
        number = int(result[:space])
        return number

    def ping(self):
        '''
        Send a ping to the system and return True if the first two bytes
        of the response are b'OK'.

        '''
        self.sender.send(b'PING_HB')
        result = self.sender.recv()
        return result[:2] == b'OK'
