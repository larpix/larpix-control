import itertools
import zmq
import bidict
import time
from collections import defaultdict
import multiprocessing
import sys
if sys.version_info[0] >= 3:
    from queue import Empty
else:
    from Queue import Empty
import os

from larpix.io import IO
from larpix.configs import load
import larpix.format.pacman_msg_format as pacman_msg_format
import larpix.format.rawhdf5format as rawhdf5format
from larpix import Packet_v2

class PACMAN_IO(IO):
    '''
    The PACMAN_IO object interfaces with a network of PACMAN
    boards each running a pacman-cmdserver and pacman-dataserver.

    This object handles the ZMQ messaging protocol to send and receive
    formatted messages to/from the PACMAN boards. If you want more
    info on how messages are formatted, see ``larpix.format.pacman_msg_format``.

    The PACMAN_IO object has five flags for optimizing communications
    which you may or may not want to enable:

        - ``group_packets_by_io_group``
        - ``interleave_packets_by_io_channel``
        - ``double_send_packets``
        - ``enable_raw_file_writing``
        - ``disable_packet_parsing``

    To enable each option set the flag to ``True``; to disable, set to
    ``False``.

        - The ``group_packets_by_io_group`` option is enabled by default and assembles the packets sent in each call to ``send`` into as few messages as possible destined for a single io group. E.g. sending three packets (2 for ``io_group=1``, 1 for ``io_group=2``) will combine the packets for ``io_group=1`` into a single message to transfer over the network. This reduces overhead associated with network latency and allows large data transfers to happen much faster.

        - The ``interleave_packets_by_io_channel`` option is enabled by default and interleaves packets within a given message to each io_channel on a given io_group. E.g. 3 packets destined for ``io_channel=1``, ``io_channel=1``, and ``io_channel=2`` will be reordered to ``io_channel=1``, ``io_channel=2``, and ``io_channel=1``. The order of the packets is preserved for each io_channel. This increases the data throughput by about a factor of N, where N is the number of io channels in the message.

        - The ``double_send_packets`` option is disabled by default and duplicates each packet sent to the PACMAN by a call to ``send()``. This is potentially useful for working around the 512 bug when you need to insure that a packet reaches a chip, but you don't care about introducing extra packets into the system (i.e. when configuring chips).

        - The ``enable_raw_file_writing`` option will directly dump data to a larpix raw hdf5 formatted file. This is used as a more performant means of logging data (see ``larpix.format.rawhdf5format``). The data file name can be accessed or changed via the ``raw_filename`` attribute, or can be set when creating the ``PACMAN_IO`` object with the ``raw_directory`` and ``raw_filename`` keyword args.

        - The ``disable_packet_parsing`` option will skip converting PACMAN messages into ``larpix.packet`` types. Thus if ``disable_packet_parsing=True``, every call to ``empty_queue`` will return ``[], b''``. Typically used in conjunction with ``enable_raw_file_writing``, this allows the PACMAN_IO class to read data much faster.


    '''
    default_filepath = 'io/pacman.json'
    default_raw_filename_fmt = 'raw_%Y_%m_%d_%H_%M_%S_%Z.h5'
    max_msg_length = 2**16-1
    cmdserver_port = '5555'
    dataserver_port = '5556'
    _valid_config_classes = ['PACMAN_IO']

    group_packets_by_io_group = True
    interleave_packets_by_io_channel = True
    double_send_packets = False
    enable_raw_file_writing = False
    disable_packet_parsing = False

    _base_ctrl_reg = 0x10
    _clk_ctrl_reg = 0x1010
    _sw_reset_cycles_reg = 0x1014
    _channel_offset = 0x2000
    _channel_size = 0x1000
    _uart_clock_ratio_offset = 0x10
    _vddd_dac_reg = 0x24001
    _vdda_dac_reg = 0x24011
    _vddd_adc_reg = 0x24032
    _vdda_adc_reg = 0x24042
    _iddd_adc_reg = 0x24031
    _idda_adc_reg = 0x24041
    _vplus_adc_reg = 0x24022
    _iplus_adc_reg = 0x24021
    _adc2mv = lambda _,x: ((x >> 16) >> 3) * 4
    _adc2ma = lambda _,x: ((x >> 16) - (x >> 31) * 65535) * 500 * 0.01

    def __init__(self, config_filepath=None, hwm=20000, relaxed=True, timeout=-1, raw_directory='./', raw_filename=None):
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
            receiver.setsockopt(zmq.CONNECT_TIMEOUT,max(timeout,0))
            receiver.setsockopt(zmq.LINGER,0)
            receiver.setsockopt(zmq.RCVTIMEO,timeout)
        for sender in self.senders.values():
            if relaxed:
                sender.setsockopt(zmq.REQ_RELAXED,True)
            sender.setsockopt(zmq.LINGER,0)
            sender.setsockopt(zmq.CONNECT_TIMEOUT,max(timeout,0))
            sender.setsockopt(zmq.RCVTIMEO,timeout)
            sender.setsockopt(zmq.SNDTIMEO,timeout)
        for address in self._io_group_table.inv:
            send_address = 'tcp://' + address + ':' + self.cmdserver_port
            receive_address = 'tcp://' + address + ':' + self.dataserver_port
            self.senders[address].connect(send_address)
            self.receivers[address].connect(receive_address)
        self._sender_replies = defaultdict(list)
        self.poller = zmq.Poller()
        for receiver in self.receivers.values():
            self.poller.register(receiver, zmq.POLLIN)

        self._raw_file_queue = multiprocessing.Queue()
        self.raw_filename = os.path.join(
            raw_directory,
            raw_filename if raw_filename is not None \
                else time.strftime(self.default_raw_filename_fmt)
        )
        self._launch_raw_file_worker()

    def send(self, packets):
        '''
        Sends a request message to PACMAN boards to send designated
        packets.

        '''
        msg_packets = list()
        # group packets into messages destined for a single io group (otherwise 1pkt = 1msg)
        if self.group_packets_by_io_group:
            grouped_packets = self._group_by_attr(packets, 'io_group')
            for io_group, packets in grouped_packets.items():
                msg_packets.append(packets)
        else:
            for packet in packets:
                msg_packets.append([packet])

        # interleave across io group channels
        if self.interleave_packets_by_io_channel and self.group_packets_by_io_group:
            interleaved_msg_packets = list()
            for packets in msg_packets:
                interleaved_msg_packets.append(self._interleave_by_attr(packets, 'io_channel'))
            msg_packets = interleaved_msg_packets

        # double up sent packets to help avoid 512 bug
        if self.double_send_packets:
            doubled_msg_packets = list()
            for packets in msg_packets:
                for _ in range(2):
                    doubled_msg_packets.append(packets)
            msg_packets = doubled_msg_packets

        # convert packets to messages
        resp_addresses = list()
        for packets in msg_packets:
            io_group = packets[0].io_group
            for i in range(0, len(packets), self.max_msg_length):
                #for packet in packets: print(packet)
                msg_len = min(len(packets)-i, self.max_msg_length)
                msg = pacman_msg_format.format(packets[i:i+msg_len], msg_type='REQ')
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
        if not self.disable_packet_parsing:
            for message, address in zip(bytestream_list, address_list):
                packets += pacman_msg_format.parse(message, io_group=self._io_group_table.inv[address])
            bytestream = b''.join(bytestream_list)
        if self.enable_raw_file_writing:
            self._raw_file_queue.put((bytestream_list, [self._io_group_table.inv[address] for address in address_list]))
            if not self._raw_file_worker.is_alive():
                self._launch_raw_file_worker()

        return packets,bytestream

    def cleanup(self):
        '''
        Close the ZMQ objects to prevent a memory leak.

        This method is only required if you plan on instantiating a new
        ``PACMAN_IO`` object.

        '''
        for address in self.senders.keys():
            self.senders[address].close(linger=0)
            self.receivers[address].close(linger=0)
        self.context.term()

    @staticmethod
    def _to_raw_file(queue_, filename, timeout=1, max_msgs=100000):
        start_time = time.time()
        while (time.time() < start_time + timeout or not queue_.empty()):
            # wait for data
            try:
                msgs, io_groups = queue_.get(timeout=timeout)
            except Empty:
                continue
            # buffer data
            while len(msgs) < max_msgs:
                try:
                    new_msgs, new_io_groups = queue_.get(False)
                    msgs.extend(new_msgs)
                    io_groups.extend(new_io_groups)
                except Empty:
                    break
            # write to file
            if len(msgs):
                rawhdf5format.to_rawfile(filename, msgs=msgs, msg_headers={'io_groups': io_groups}, io_version=pacman_msg_format.latest_version)
                start_time = time.time()

    def _launch_raw_file_worker(self):
        self._raw_file_worker = multiprocessing.Process(target=self._to_raw_file, args=(self._raw_file_queue, self.raw_filename))
        self._raw_file_worker.start()

    def join(self):
        '''
        Wait for raw file worker to finish

        '''
        self._raw_file_worker.join()

    @property
    def raw_filename(self):
        return self._raw_filename

    @raw_filename.setter
    def raw_filename(self,value):
        if hasattr(self,'_raw_filename') \
                and value != self._raw_filename \
                and self._raw_file_worker.is_alive():
            self.join()
        self._raw_filename = value

    def set_reg(self, reg, val, io_group=None):
        '''
        Set a 32-bit register in the pacman PL

        '''
        if io_group is None:
            return dict([(io_group,self.set_reg(reg, val, io_group=io_group)) for io_group in self._io_group_table])
        msg = pacman_msg_format.format_msg('REQ',[('WRITE',reg,val)])
        addr = self._io_group_table[io_group]
        self.senders[addr].send(msg)
        self._sender_replies[addr].append(self.senders[addr].recv())

    def get_reg(self, reg, io_group=None):
        '''
        Read a 32-bit register from the pacman PL

        If no ``io_group`` is specified, returns a ``dict`` of ``io_group, reg_value``
        else returns reg_value

        '''
        if io_group is None:
            return dict([(io_group, self.get_reg(reg, io_group=io_group)) for io_group in self._io_group_table])
        msg = pacman_msg_format.format_msg('REQ',[('READ',reg,0)])
        addr = self._io_group_table[io_group]
        self.senders[addr].send(msg)
        self._sender_replies[addr].append(self.senders[addr].recv())
        msg_data = pacman_msg_format.parse_msg(self._sender_replies[addr][-1])
        if msg_data[1][0][0] == 'READ':
            return msg_data[1][0][-1]
        raise RuntimeError('Error received from server')

    def ping(self, io_group=None):
        '''
        Send a ping message

        If no ``io_group`` is specified, returns a ``dict`` of ``io_group, response``
        else returns response

        '''
        if io_group is None:
            return dict([(io_group, self.ping(io_group=io_group)) for io_group in self._io_group_table])
        msg = pacman_msg_format.format_msg('REQ',[('PING',)])
        addr = self._io_group_table[io_group]
        try:
            self.senders[addr].send(msg)
            self._sender_replies[addr].append(self.senders[addr].recv())
            msg_data = pacman_msg_format.parse_msg(self._sender_replies[addr][-1])
            if msg_data[1][0][0] == 'PONG':
                return True
        except zmq.ZMQError as e:
            print('IO error on {}: {}'.format(io_group,e))
        return False

    def get_vddd(self, io_group=None):
        '''
        Gets PACMAN VDDD voltage

        Returns VDDD and IDDD values from the built-in ADC as
        a tuple of mV and mA respectively

        '''
        if io_group is None:
            return dict([(io_group, self.get_vddd(io_group=io_group)) for io_group in self._io_group_table])
        mv = self._adc2mv(self.get_reg(self._vddd_adc_reg, io_group=io_group))
        ma = self._adc2ma(self.get_reg(self._iddd_adc_reg, io_group=io_group))
        return mv, ma

    def set_vddd(self, vddd_dac=0xD5A3, io_group=None, settling_time=0.1):
        '''
        Sets PACMAN VDDD voltage

        If no ``vddd_dac`` value is specified, sets VDDD to default of ~1.8V

        Returns the resulting VDDD and IDDD values from the built-in ADC as
        a tuple of mV and mA respectively

        '''
        if io_group is None:
            return dict([(io_group, self.set_vddd(vddd_dac, io_group=io_group)) for io_group in self._io_group_table])
        self.set_reg(self._vddd_dac_reg, vddd_dac, io_group=io_group)
        if settling_time:
            time.sleep(settling_time)
        return self.get_vddd(io_group=io_group)

    def get_vdda(self, io_group=None):
        '''
        Gets PACMAN VDDA voltage

        Returns VDDA and IDDA values from the built-in ADC as
        a tuple of mV and mA respectively

        '''
        if io_group is None:
            return dict([(io_group, self.get_vdda(io_group=io_group)) for io_group in self._io_group_table])
        mv = self._adc2mv(self.get_reg(self._vdda_adc_reg, io_group=io_group))
        ma = self._adc2ma(self.get_reg(self._idda_adc_reg, io_group=io_group))
        return mv, ma

    def set_vdda(self, vdda_dac=0xD5A3, io_group=None, settling_time=0.1):
        '''
        Sets PACMAN VDDA voltage

        If no ``vdda_dac`` value is specified, sets VDDA to default of ~1.8V

        Returns the resulting VDDA and IDDA values from the built-in ADC as
        a tuple of mV and mA respectively

        '''
        if io_group is None:
            return dict([(io_group, self.set_vdda(vdda_dac, io_group=io_group)) for io_group in self._io_group_table])
        self.set_reg(self._vdda_dac_reg, vdda_dac, io_group=io_group)
        if settling_time:
            time.sleep(settling_time)
        return self.get_vdda(io_group=io_group)

    def get_vplus(self, io_group=None):
        '''
        Gets PACMAN Vplus voltage

        Returns Vplus and Iplus values from the built-in ADC as
        a tuple of mV and mA respectively

        '''
        if io_group is None:
            return dict([(io_group, self.get_vplus(io_group=io_group)) for io_group in self._io_group_table])
        mv = self._adc2mv(self.get_reg(self._vplus_adc_reg, io_group=io_group))
        ma = self._adc2ma(self.get_reg(self._iplus_adc_reg, io_group=io_group))
        return mv, ma

    def enable_tile(self, tile_indices=None, io_group=None):
        '''
        Enables the specified pixel tile(s) (first tile is index=0, second
        tile is index=1, ...).

        Returns the value of the new tile enable mask

        '''
        if io_group is None:
            return dict([(io_group, self.enable_tile(tile_indices=tile_indices, io_group=io_group)) for io_group in self._io_group_table])
        if tile_indices is None:
            tile_indices = list(range(8))
        elif isinstance(tile_indices,int):
            tile_indices = [tile_indices]
        val = self.get_reg(self._base_ctrl_reg, io_group=io_group)
        for idx in tile_indices:
            val = val | (1 << idx)
        self.set_reg(self._base_ctrl_reg, val, io_group=io_group)
        return (self.get_reg(self._base_ctrl_reg, io_group=io_group) & 0xFF)

    def disable_tile(self, tile_indices=None, io_group=None):
        '''
        Disables the specified pixel tile(s) (first tile is index=0, second
        tile is index=1, ...).

        Returns the value of the new tile enable mask

        '''
        if io_group is None:
            return dict([(io_group, self.disable_tile(tile_indices=tile_indices, io_group=io_group)) for io_group in self._io_group_table])
        if tile_indices is None:
            tile_indices = list(range(8))
        elif isinstance(tile_indices,int):
            tile_indices = [tile_indices]
        val = self.get_reg(self._base_ctrl_reg, io_group=io_group)
        for idx in tile_indices:
            val = val & (0xFFFFFFFF & ~(1 << idx))
        self.set_reg(self._base_ctrl_reg, val, io_group=io_group)
        return (self.get_reg(self._base_ctrl_reg, io_group=io_group) & 0xFF)

    def set_uart_clock_ratio(self, channel, ratio, io_group=None):
        '''
        Sets PACMAN UART clock speed relative to the larpix master clock
        for the specified channel

        For a nominal 10MHz clock, a ratio value of 4 results in a 2.5MHz
        UART clock.

        Returns the value of the UART clock register that was set

        '''
        if io_group is None:
            return dict([(io_group, self.set_uart_clock_ratio(channel, ratio, io_group=io_group)) for io_group in self._io_group_table])
        reg = self._channel_size*channel + self._uart_clock_ratio_offset + self._channel_offset
        self.set_reg(reg, ratio, io_group=io_group)
        return self.get_reg(reg, io_group=io_group)

    def reset_larpix(self, length=256, io_group=None):
        '''
        Issues a reset of the specified length (in larpix MCLK cycles).

        If no ``length`` specified, issue a hard reset.

        Returns the value of the clock/reset control register after the reset

        '''
        if io_group is None:
            return dict([(io_group, self.reset_larpix(length, io_group=io_group)) for io_group in self._io_group_table])
        # set reset cycles
        self.set_reg(self._sw_reset_cycles_reg, length, io_group=io_group)
        # toggle reset bit
        clk_ctrl = self.get_reg(self._clk_ctrl_reg, io_group=io_group)
        self.set_reg(self._clk_ctrl_reg, clk_ctrl|4, io_group=io_group)
        self.set_reg(self._clk_ctrl_reg, clk_ctrl, io_group=io_group)
        return self.get_reg(self._clk_ctrl_reg, io_group=io_group)

