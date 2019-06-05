import time
import zmq
import sys
from collections import defaultdict

from larpix.io import IO
from larpix.larpix import Packet

class MultiZMQ_IO(IO):
    '''
    The MultiZMQ_IO object interfaces with a network of Bern LArPix v2 modules
    using Igor's ZeroMQ communications protocol.

    This object handles the required communications, and also has extra
    methods for additional functionality, including system reset, packet
    count, clock frequency, and more.

    '''

    def __init__(self, addresses):
        super(MultiZMQ_IO, self).__init__()
        if not isinstance(addresses, list):
            raise ValueError('MultiZMQ_IO must be instaniated with a list of '
                'board addresses')
        self.context = zmq.Context()
        self.senders = {}
        self.senders_lookup = {}
        self.receivers = {}
        self.receivers_lookup = {}
        for address in addresses:
            self.senders[address] = self.context.socket(zmq.REQ)
            self.receivers[address] = self.context.socket(zmq.SUB)
            self.senders_lookup[self.senders[address]] = address
            self.receivers_lookup[self.receivers[address]] = address
        self.hwm = 20000
        for receiver in self.receivers.values():
            receiver.set_hwm(self.hwm)
        for address in self.senders.keys():
            send_address = 'tcp://' + address + ':5555'
            receive_address = 'tcp://' + address + ':5556'
            self.senders[address].connect(send_address)
            self.receivers[address].connect(receive_address)
        self.sender_replies = defaultdict(list)
        self.poller = zmq.Poller()
        for receiver in self.receivers.values():
            self.poller.register(receiver, zmq.POLLIN)

    def send(self, packets):
        self.sender_replies = defaultdict(list)
        send_time = time.time()
        addresses = [self.parse_chip_key(packet.chip_key)['address'] for packet in packets]
        msg_datas = self.encode(packets)
        for address, msg_data in zip(addresses, msg_datas):
            tosend = b'SNDWORD ' + msg_data
            self.senders[address].send(tosend)
            self.sender_replies[address].append(self.senders[address].recv())

    def start_listening(self):
        if self.is_listening:
            raise RuntimeError('Already listening')
        super(MultiZMQ_IO, self).start_listening()
        for receiver in self.receivers.values():
            receiver.setsockopt(zmq.SUBSCRIBE, b'')

    def stop_listening(self):
        if not self.is_listening:
            raise RuntimeError('Already not listening')
        super(MultiZMQ_IO, self).stop_listening()
        for receiver in self.receivers.values():
            receiver.setsockopt(zmq.UNSUBSCRIBE, b'')

    @classmethod
    def is_valid_chip_key(cls, key):
        '''
        Valid chip keys must be strings formatted as:
        ``'<daq_address>/<io_chain>/<chip_id>'``
        Note that ``/`` is a special character and should not be used
        in daq address

        '''
        if not super(cls, cls).is_valid_chip_key(key):
            return False
        if not isinstance(key, str):
            return False
        parsed_key = key.split('/')
        if not len(parsed_key) == 3:
            return False
        try:
            _ = int(parsed_key[1])
            _ = int(parsed_key[2])
        except ValueError:
            return False
        return True

    @classmethod
    def parse_chip_key(cls, key):
        '''
        Decodes a chip key into ``'chip_id'``, ``'io_chain'``, and ``'address'``

        :returns: ``dict`` with keys ``('chip_id', 'io_chain', 'addresss')``
        '''
        return_dict = super(cls, cls).parse_chip_key(key)
        parsed_key = key.split('/')
        return_dict['chip_id'] = int(parsed_key[2])
        return_dict['io_chain'] = int(parsed_key[1])
        return_dict['address'] = parsed_key[0]
        return return_dict

    @classmethod
    def generate_chip_key(cls, **kwargs):
        '''
        Generates a valid ``MultiZMQ_IO`` chip key

        :param chip_id: ``int`` corresponding to internal chip id

        :param io_chain: ``int`` corresponding to daisy chain number

        :param address: ``str`` corresponding to address of DAQ board

        '''
        req_fields = ('chip_id', 'io_chain', 'address')
        if not all([key in kwargs for key in req_fields]):
            raise ValueError('Missing fields required to generate chip id'
                ', requires {}, received {}'.format(req_fields, kwargs.keys()))
        if not isinstance(kwargs['chip_id'], int):
            raise ValueError('chip_id must be int')
        if not isinstance(kwargs['io_chain'], int):
            raise ValueError('io_chain must be int')
        if not isinstance(kwargs['address'], str):
            raise ValueError('address must be str')
        return '{address}/{io_chain}/{chip_id}'.format(**kwargs)

    @classmethod
    def decode(cls, msgs, io_chain=0, address=None, **kwargs):
        '''
        Convert a list ZMQ messages into packets

        '''
        packets = []
        for msg in msgs:
            if len(msg) % 8 == 0:
                for start_index in range(0, len(msg), 8):
                    packet_bytes = msg[start_index:start_index+7]
                    packets.append(Packet(packet_bytes))
                    packets[-1].chip_key = cls.generate_chip_key(
                        chip_id=packets[-1].chipid, io_chain=io_chain, address=str(address))
        return packets

    @classmethod
    def encode(cls, packets):
        '''
        Encode a list of packets into ZMQ messages
        '''
        msg_data = []
        if sys.version_info[0] < 3:
            msg_data = [b'0x00%s 0' % packet.bytes()[::-1].encode('hex') for packet in packets]
        else:
            msg_data = [b'0x00%s 0' % packet.bytes()[::-1].hex().encode() for packet in packets]
        return msg_data

    def empty_queue(self):
        '''
        Process any awaiting messages from all ZMQ connections. Will continue
        to read until the `hwm` is reached or there are no more awaiting messages.

        :returns: 2-`tuple` containing a list of received packets and the full bytestream
        '''
        packets = []
        bytestream_list = []
        bytestream = b''
        n_recv = 0
        read_time = time.time()
        while self.poller.poll(0) and n_recv < self.hwm:
            events = dict(self.poller.poll(0))
            for socket, n_events in events.items():
                for _ in range(n_events):
                    message = socket.recv()
                    n_recv += 1
                    bytestream_list.append(message)
                    packets += self.decode([message], io_chain=0, address=self.receivers_lookup[socket])
        #print('len(bytestream_list) = %d' % len(bytestream_list))
        bytestream = b''.join(bytestream_list)
        return packets, bytestream

    def reset(self, addresses=None):
        '''
        Send a reset pulse to the LArPix ASICs.

        :param addresses: ``list`` of daq board addresses to reset, if ``None`` reset all addresses

        '''
        if addresses is None:
            return self.reset(addresses=self.senders.keys())

        for address in addresses:
            self.senders[address].send(b'SYRESET')
        return_dict = {}
        for address in addresses:
            return_dict[address] = self.senders[address].recv()
        return return_dict

    def set_clock(self, freq_khz, addresses=None):
        '''
        Set the LArPix CLK2X freqency (in kHz).

        :param freq_khz: CLK2X freq in khz to set

        :param addresses: ``list`` of daq board addresses to change frequency, if ``None`` modifies all addresses

        '''
        if addresses is None:
            return self.set_clock(freq_khz, addresses=self.senders.keys())

        for address in addresses:
            self.senders[address].send(b'SETFREQ %s' % hex(freq_khz).encode())
        return_dict = {}
        for address in addresses:
            return_dict[address] = self.senders[address].recv()
        return return_dict

    def set_testpulse_freq(self, divisor, address):
        '''
        Set the testpulse frequency, computed by dividing the CLK2X
        frequency by ``divisor``.

        :param divisor: test pulse frequency divisor

        :param address: daq board addresses to change test pulse freq

        '''
        self.senders[address].send(b'SETFTST %s' % hex(divisor).encode())
        return self.senders[address].recv()

    def get_packet_count(self, io_channel, address):
        '''
        Get the number of packets received, as determined by the number
        of UART "start" bits processed.

        :param io_channel: IO channel to check

        :param address: address of daq board

        '''
        self.senders[address].send(b'GETSTAT %d' % io_channel)
        result = self.senders[address].recv()
        space = result.find(b' ')
        number = int(result[:space])
        return number

    def ping(self, addresses=None):
        '''
        Send a ping to the system.

        :param addresses: ``list`` of daq board addresses to ping, if ``None`` ping all addresses

        :returns: ``dict`` with one entry per address. Value is ``True`` if first two bytes of the response are b'OK'.

        '''
        if addresses is None:
            return self.ping(addresses=self.senders.keys())

        for address in addresses:
            self.senders[address].send(b'PING_HB')
        result = {}
        for address in addresses:
            received_msg = self.senders[address].recv()
            result[address] = received_msg[:2] == b'OK'
        return result
