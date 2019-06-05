import time
import zmq
import sys

from larpix.io import IO
from larpix.io.multizmq_io import MultiZMQ_IO
from larpix.larpix import Packet

class ZMQ_IO(IO):
    '''
    The ZMQ_IO object interfaces with the Bern LArPix v2 module using
    the ZeroMQ communications protocol. This class wraps the
    ``io.multizmq_io.MultiZMQ_IO`` class, and enables a slightly simpler chip
    key formatting in the special case that you are only interfacing with a
    single daq board.

    This object handles the required communications, and also has extra
    methods for additional functionality, including system reset, packet
    count, clock frequency, and more.

    '''

    def __init__(self, address):
        super(ZMQ_IO, self).__init__()
        self._io = MultiZMQ_IO(addresses=[address])
        self._address = address

    @property
    def context(self):
        return self._io.context
    @context.setter
    def context(self, val):
        self._io.context = val

    @property
    def sender(self):
        return self._io.senders[self._address]
    @sender.setter
    def sender(self, val):
        self._io.senders[self._address] = val

    @property
    def receiver(self):
        return self._io.receivers[self._address]
    @receiver.setter
    def receiver(self, val):
        self._io.receivers[self._address] = val

    @property
    def hwm(self):
        return self._io.hwm
    @hwm.setter
    def hwm(self, val):
        self._io.hwm = val

    @property
    def poller(self):
        return self._io.poller
    @poller.setter
    def poller(self, val):
        self._io.poller = val

    @property
    def sender_replies(self):
        return self._io.sender_replies[self._address]
    @sender_replies.setter
    def sender_replies(self, val):
        self._io.sender_replies[self._address] = val

    def send(self, packets):
        for packet in packets:
            packet.chip_key = self._io.generate_chip_key(address=self._address,
                **self.parse_chip_key(packet.chip_key))
        self._io.send(packets)

    def start_listening(self):
        self._io.start_listening()

    def stop_listening(self):
        self._io.stop_listening()

    @classmethod
    def is_valid_chip_key(cls, key):
        '''
        Valid chip keys must be strings formatted as:
        ``'<io_chain>/<chip_id>'``

        '''
        if not super(cls, cls).is_valid_chip_key(key):
            return False
        if not isinstance(key, str):
            return False
        parsed_key = key.split('/')
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
        parsed_key = key.split('/')
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
        return '{io_chain}/{chip_id}'.format(**kwargs)

    @classmethod
    def decode(cls, msgs, io_chain=0, **kwargs):
        '''
        Convert a list ZMQ messages into packets
        '''
        packets = MultiZMQ_IO.decode(msgs, io_chain=io_chain, address=None, **kwargs)
        for packet in packets:
            packet.chip_key = cls.generate_chip_key(**MultiZMQ_IO.parse_chip_key(packet.chip_key))
        return packets

    @classmethod
    def encode(cls, packets):
        '''
        Encode a list of packets into ZMQ messages
        '''
        return MultiZMQ_IO.encode(packets)

    def empty_queue(self):
        packets, bytestream = self._io.empty_queue()
        for packet in packets:
            packet.chip_key = self.generate_chip_key(**self._io.parse_chip_key(packet.chip_key))
        return packets, bytestream

    def reset(self):
        '''
        Send a reset pulse to the LArPix ASICs.

        '''
        return self._io.reset()[self._address]

    def set_clock(self, freq_khz):
        '''
        Set the LArPix CLK2X freqency (in kHz).

        '''
        return self._io.set_clock(freq_khz)[self._address]

    def set_testpulse_freq(self, divisor):
        '''
        Set the testpulse frequency, computed by dividing the CLK2X
        frequency by ``divisor``.

        '''
        return self._io.set_testpulse_freq(divisor=divisor, address=self._address)[self._address]

    def get_packet_count(self, io_channel):
        '''
        Get the number of packets received, as determined by the number
        of UART "start" bits processed.

        '''
        return self._io.get_packet_count(io_channel=io_channel, address=self._address)[self._address]

    def ping(self):
        '''
        Send a ping to the system and return True if the first two bytes
        of the response are b'OK'.

        '''
        return self._io.ping()[self._address]
