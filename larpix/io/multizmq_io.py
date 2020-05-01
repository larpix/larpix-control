import time
import zmq
import sys
from collections import defaultdict
import warnings
import bidict

from larpix.io import IO
from larpix import Packet, Key, Packet_v2, Packet_v1
from larpix.configs import load
from larpix.format.message_format import dataserver_message_decode

class MultiZMQ_IO(IO):
    '''
    The MultiZMQ_IO object interfaces with a network of Bern LArPix v2 modules
    using Igor's ZeroMQ communications protocol.

    This object handles the required communications, and also has extra
    methods for additional functionality, including system reset, packet
    count, clock frequency, and more.

    By default, when creating a MultiZMQ_IO object, the ``io/default.json``
    configuration will attempt to be loaded unless otherwise specified. The path relative to the pwd is checked first,
    followed by the path of the larpix-control installation.

    '''
    _valid_config_classes = ['MultiZMQ_IO']

    def __init__(self, config_filepath=None, miso_map=None, mosi_map=None):
        super(MultiZMQ_IO, self).__init__()
        self.load(config_filepath)

        if miso_map is None:
            self._miso_map = {}
        else:
            self._miso_map = miso_map
        if mosi_map is None:
            self._mosi_map = {}
        else:
            self._mosi_map = mosi_map

        self.context = zmq.Context()
        self.senders = bidict.bidict()
        self.receivers = bidict.bidict()
        for address in self._io_group_table.inv:
            self.senders[address] = self.context.socket(zmq.REQ)
            self.receivers[address] = self.context.socket(zmq.SUB)
        self.hwm = 20000
        for receiver in self.receivers.values():
            receiver.set_hwm(self.hwm)
        for address in self._io_group_table.inv:
            send_address = 'tcp://' + address + ':5555'
            receive_address = 'tcp://' + address + ':5556'
            self.senders[address].connect(send_address)
            self.receivers[address].connect(receive_address)
        self._sender_replies = defaultdict(list)
        self.poller = zmq.Poller()
        for receiver in self.receivers.values():
            self.poller.register(receiver, zmq.POLLIN)

    @property
    def sender_replies(self):
        return self._sender_replies
    @sender_replies.setter
    def sender_replies(self, val):
        self._sender_replies = val

    def send(self, packets):
        self.sender_replies = defaultdict(list)
        send_time = time.time()
        addresses = [self._io_group_table[packet.io_group] for packet in packets]
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

    def decode(self, msgs, address, **kwargs):
        '''
        Convert a list ZMQ messages into packets

        '''
        return_packets = dataserver_message_decode(msgs, version=(1,0), io_group=self._io_group_table.inv[address], **kwargs)
        if self._miso_map.keys():
            for packet in return_packets:
                if hasattr(packet, 'io_channel') and packet.io_channel in self._miso_map.keys():
                    packet.io_channel = self._miso_map[packet.io_channel]
        return return_packets

    def encode(self, packets):
        '''
        Encode a list of packets into ZMQ messages
        '''
        msg_data = []
        for packet in packets:
            io_chain = packet.io_channel
            if io_chain in self._mosi_map.keys():
                io_chain = self._mosi_map[io_chain]
            fmt_bytestr = b'0x%s %d'
            if isinstance(packet, Packet_v1):
                fmt_bytestr = b'0x00%s %d'
            if sys.version_info[0] < 3:
                msg_data += [fmt_bytestr % (packet.bytes()[::-1].encode('hex'), io_chain)]
            else:
                msg_data += [fmt_bytestr % (packet.bytes()[::-1].hex().encode(), io_chain)]
        print(msg_data)
        return msg_data

    def empty_queue(self):
        '''
        Process any awaiting messages from all ZMQ connections. Will continue
        to read until the `hwm` is reached or there are no more awaiting messages.

        :returns: 2-`tuple` containing a list of received packets and the full bytestream
        '''
        packets = []
        address_list = []
        bytestream_list = []
        bytestream = b''
        n_recv = 0
        read_time = time.time()
        message = ''
        while self.poller.poll(0) and n_recv < self.hwm:
            events = dict(self.poller.poll(0))
            for socket, n_events in events.items():
                for _ in range(n_events):
                    message = socket.recv()
                    n_recv += 1
                    bytestream_list += [message]
                    address_list += [self.receivers.inv[socket]]
        for message, address in zip(bytestream_list, address_list):
            #print(message)
            packets += self.decode([message], address=address)
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

    def cleanup(self):
        '''
        Close the ZMQ objects to prevent a memory leak.

        This method is only required if you plan on instantiating a new
        ``MultiZMQ_IO`` object.

        '''
        for address in self.senders.keys():
            self.senders[address].close(linger=0)
            self.receivers[address].close(linger=0)
        self.context.term()
