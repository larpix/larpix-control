import itertools
import zmq
import bidict
from collections import defaultdict

from larpix.io import IO
from larpix.configs import load
import larpix.format.pacman_msg_format as pacman_msg_format

class PACMAN_IO(IO):
    '''
    The PACMAN_IO object interfaces with a network of PACMAN
    boards each running a pacman-cmdserver and pacman-dataserver.

    This object handles the ZMQ messaging protocol to send and receive
    formatted messages to/from the PACMAN boards. If you want more
    info on how messages are formatted, see `larpix.format.pacman_msg_format`.

    '''
    max_msg_length = 2**16-1
    cmdserver_port = '5555'
    dataserver_port = '5556'
    _valid_config_classes = ['PACMAN_IO']

    def __init__(self, config_filepath=None, hwm=20000):
        super(PACMAN_IO, self).__init__()
        self.load(config_filepath)

        self.context = zmq.Context()
        self.senders = bidict.bidict()
        self.receivers = bidict.bidict()
        for address in self._io_group_table.inv:
            self.senders[address] = self.context.socket(zmq.REQ)
            self.receivers[address] = self.context.socket(zmq.SUB)
        self.hwm = hwm
        for receiver in self.receivers.values():
            receiver.set_hwm(self.hwm)
        for address in self._io_group_table.inv:
            send_address = 'tcp://' + address + ':' + self.cmdserver_port
            receive_address = 'tcp://' + address + ':' + self.dataserver_port
            self.senders[address].connect(send_address)
            self.receivers[address].connect(receive_address)
        self._sender_replies = defaultdict(list)
        self.poller = zmq.Poller()
        for receiver in self.receivers.values():
            self.poller.register(receiver, zmq.POLLIN)

    def send(self, packets, group_by_io_group=True, interleave_by_io_channel=True):
        '''
        Sends a request message to PACMAN boards to send designated
        packets.

        By default, groups all packets destined for same PACMAN board
        into a single message, otherwise sends each packet in new
        message (slow if many packets).

        By default, packets will be interleaved across io channels,
        e.g <ch0>, <ch1>, <ch0>, <ch1>, <ch0>, <ch0>, ... This allows
        the PACMAN board to transmit the data in a parallel fashion
        (~8x speed up when sending data to multiple channels).

        '''
        msg_packets = list()
        # group packets into messages destined for a single io group (otherwise 1pkt = 1msg)
        if group_by_io_group:
            grouped_packets = self._group_by_attr(packets, 'io_group')
            for io_group, packets in grouped_packets.items():
                msg_packets.append(packets)
        else:
            msg_packets = packets

        # interleave across io group channels
        if interleave_by_io_channel and group_by_io_group:
            interleaved_msg_packets = list()
            for packets in msg_packets:
                interleaved_msg_packets.append(self._interleave_by_attr(packets, 'io_channel'))
            msg_packets = interleaved_msg_packets

        # convert packets to messages
        resp_addresses = list()
        for packets in msg_packets:
            io_group = packets[0].io_group
            for i in range(0, len(packets), self.max_msg_length):
                msg = pacman_msg_format.format(packets, msg_type='REQ')
                address = self._io_group_table[io_group]
                self.senders[address].send(msg)
                self._sender_replies[address].append(self.senders[address].recv())

    def start_listening(self):
        '''
        Start keeping msgs from data server

        '''
        if self.is_listening:
            raise RuntimeError('Already listening')
        super(PACMAN_IO, self).start_listening()
        for receiver in self.receivers.values():
            receiver.setsockopt(zmq.SUBSCRIBE, b'')

    def stop_listening(self):
        '''
        Stop keeping msgs from data server

        '''
        if not self.is_listening:
            raise RuntimeError('Already not listening')
        super(PACMAN_IO, self).stop_listening()
        for receiver in self.receivers.values():
            receiver.setsockopt(zmq.UNSUBSCRIBE, b'')

    @staticmethod
    def _group_by_attr(packets, attr):
        '''
        Groups packets by the specified attribute
        returns a dict of attr_value: [<packets w/ attr=attr_value>]

        '''
        groupings = defaultdict(list)
        for packet in packets:
            groupings[getattr(packet,attr)].append(packet)
        return groupings

    @staticmethod
    def _interleave_by_attr(packets, attr):
        '''
        Interleaves packets by the specified attribute, e.g. by io channel::

            in_packets = [<ch 1>, <ch 1>, ..., <ch 2>, <ch 2>, ..]
            _interleave_by_attr(in_packets, 'io_channel')
            # returns [<ch 1>, <ch 2>, <ch 1>, <ch 2>, ... , <ch 1>, <ch 1>]

        '''

        groupings = PACMAN_IO._group_by_attr(packets, attr)
        zipped_packets = itertools.zip_longest(*groupings.values(), fillvalue=None)
        interleaved = list()
        for row in zipped_packets:
            for packet in row:
                if packet is not None:
                    interleaved.append(packet)
        return interleaved

    def empty_queue(self):
        '''
        Fetch and parse waiting packets on pacman data socket
        returns tuple of list of packets, full bytestream of all messages

        '''
        packets = []
        address_list = list()
        bytestream_list = list()
        bytestream = b''
        n_recv = 0
        while self.poller.poll(0) and n_recv < self.hwm:
            events = dict(self.poller.poll(0))
            for socket, n_events in events.items():
                for _ in range(n_events):
                    message = socket.recv()
                    n_recv += 1
                    bytestream_list += [message]
                    address_list += [self.receivers.inv[socket]]
        for message, address in zip(bytestream_list, address_list):
            packets += pacman_msg_format.parse(message, io_group=self._io_group_table.inv[address])
        bytestream = b''.join(bytestream_list)
        return packets,bytestream

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

    def set_reg(self, reg, val, io_group=None):
        '''
        Set a 32-bit register in the pacman PL

        '''
        if io_group is None:
            return [self.set_reg(reg, val, io_group=io_group) for io_group in self._io_group_table]
        msg = pacman_msg_format.format_msg('REQ',[('WRITE',reg,val)])
        addr = self._io_group_table[io_group]
        self.senders[addr].send(msg)
        self._sender_replies[addr].append(self.senders[addr].recv())

    def get_reg(self, reg, io_group=None):
        '''
        Read a 32-bit register from the pacman PL

        '''
        if io_group is None:
            return [self.get_reg(reg, io_group=io_group) for io_group in self._io_group_table]
        msg = pacman_msg_format.format_msg('REQ',[('READ',reg,0)])
        addr = self._io_group_table[io_group]
        self.senders[addr].send(msg)
        self._sender_replies[addr].append(self.senders[addr].recv())
        msg_data = pacman_msg_format.parse_msg(self._sender_replies[addr][-1])
        if msg_data[1][0][0] == 'READ':
            return msg_data[1][0][-1]
        raise RuntimeError('Error received from server')
