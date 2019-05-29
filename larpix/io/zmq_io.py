import time
import zmq

from larpix.io import IO
from larpix.larpix import Packet

class ZMQ_IO(IO):
    '''
    The ZMQ_IO object interfaces with the Bern LArPix v2 module using
    the ZeroMQ communications protocol.

    This object handles the required communications, and also has extra
    methods for additional functionality, including system reset, packet
    count, clock frequency, and more.

    '''

    def __init__(self, address):
        super(ZMQ_IO, self).__init__()
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
        self.poller = zmq.Poller()
        self.poller.register(self.receiver, zmq.POLLIN)

    def send(self, packets):
        self.sender_replies = []
        send_time = time.time()
        msg_datas = self.encode(packets)
        for msg_data in msg_datas:
            tosend = b'SNDWORD ' + msg_data
            self.sender.send(tosend)
            self.sender_replies.append(self.sender.recv())

    def start_listening(self):
        if self.is_listening:
            raise RuntimeError('Already listening')
        super(ZMQ_IO, self).start_listening()
        self.receiver.setsockopt(zmq.SUBSCRIBE, b'')

    def stop_listening(self):
        if not self.is_listening:
            raise RuntimeError('Already not listening')
        super(ZMQ_IO, self).stop_listening()
        self.receiver.setsockopt(zmq.UNSUBSCRIBE, b'')

    @classmethod
    def is_valid_chip_key(cls, key):
        '''
        Valid chip keys must be strings formatted as:
        ``'<io_chain>-<chip_id>'``

        '''
        if not super(cls, cls).is_valid_chip_key(key):
            return False
        if not isinstance(key, str):
            return False
        parsed_key = key.split('-')
        if not len(parsed_key) == 2:
            return False
        try:
            _ = int(parsed_key[0])
            _ = int(parsed_key[1])
        except ValueError:
            return False
        return True

    @classmethod
    def parse_chip_key(cls, key):
        '''
        Decodes a chip key into ``'chip_id'`` and ``io_chain``

        :returns: ``dict`` with keys ``('chip_id', 'io_chain')``
        '''
        return_dict = super(cls, cls).parse_chip_key(key)
        parsed_key = key.split('-')
        return_dict['chip_id'] = int(parsed_key[1])
        return_dict['io_chain'] = int(parsed_key[0])
        return return_dict

    @classmethod
    def generate_chip_key(cls, **kwargs):
        '''
        Generates a valid ``ZMQ_IO`` chip key

        :param chip_id: ``int`` corresponding to internal chip id

        :param io_chain: ``int`` corresponding to daisy chain number

        '''
        req_fields = ('chip_id', 'io_chain')
        if not all([key in kwargs for key in req_fields]):
            raise ValueError('Missing fields required to generate chip id'
                ', requires {}, received {}'.format(req_fields, kwargs.keys()))
        return '{io_chain}-{chip_id}'.format(**kwargs)

    @classmethod
    def decode(cls, msgs):
        '''
        Convert a list ZMQ messages into packets
        '''
        packets = []
        for msg in msgs:
            if len(msg) % 8 == 0:
                for start_index in range(0, len(msg), 8):
                    packet_bytes = msg[start_index:start_index+7]
                    packets.append(Packet(packet_bytes))
                    packets[-1].chip_key = cls.generate_chip_key(chip_id=packets[-1].chipid, io_chain=0)
        return packets

    @classmethod
    def encode(cls, packets):
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
