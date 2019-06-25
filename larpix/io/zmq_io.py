import time
import zmq
import sys
import copy

from larpix.io.multizmq_io import MultiZMQ_IO
from larpix.larpix import Packet

class ZMQ_IO(MultiZMQ_IO):
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
        super(ZMQ_IO, self).__init__(addresses=[address])
        self._address = address

    @property
    def sender(self):
        return self.senders[self._address]
    @sender.setter
    def sender(self, val):
        self.senders[self._address] = val

    @property
    def receiver(self):
        return self.receivers[self._address]
    @receiver.setter
    def receiver(self, val):
        self.receivers[self._address] = val

    @property
    def sender_replies(self):
        return super(ZMQ_IO, self).sender_replies[self._address]
    @sender_replies.setter
    def sender_replies(self, val):
        super(ZMQ_IO, self).sender_replies[self._address] = val

    def send(self, packets):
        # perform a deep copy, so that the original packet list is unchanged
        new_packets = [copy.deepcopy(packet) for packet in packets]
        for packet in new_packets:
            packet.chip_key = super(ZMQ_IO, self).generate_chip_key(address=self._address,
                **self.parse_chip_key(packet.chip_key))
        super(ZMQ_IO, self).send(new_packets)

    @classmethod
    def is_valid_chip_key(cls, key):
        '''
        Valid chip keys must be strings formatted as:
        ``'<io_chain>-<chip_id>'``

        '''
        if not super(MultiZMQ_IO, cls).is_valid_chip_key(key):
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
        if not ZMQ_IO.is_valid_chip_key(key):
            raise ValueError('invalid ZMQ_IO key: {}'.format(key))
        return_dict = {}
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

    # commented out because the inherited methods work just as well
    # @classmethod
    # def decode(cls, msgs, io_chain=0, **kwargs):
    #     '''
    #     Convert a list ZMQ messages into packets
    #     '''
    #     return super(ZMQ_IO, cls).decode(msgs, io_chain=io_chain, **kwargs)

    # def empty_queue(self):
    #     return super(ZMQ_IO, self).empty_queue()

    def reset(self):
        '''
        Send a reset pulse to the LArPix ASICs.

        '''
        return super(ZMQ_IO, self).reset(addresses=[self._address])[self._address]

    def set_clock(self, freq_khz):
        '''
        Set the LArPix CLK2X freqency (in kHz).

        :param freq_khz: CLK2X freq in khz to set

        '''
        return super(ZMQ_IO, self).set_clock(freq_khz=freq_khz, addresses=[self._address])[self._address]

    def set_testpulse_freq(self, divisor):
        '''
        Set the testpulse frequency, computed by dividing the CLK2X
        frequency by ``divisor``.

        '''
        return super(ZMQ_IO, self).set_testpulse_freq(divisor=divisor, address=self._address)

    def get_packet_count(self, io_channel):
        '''
        Get the number of packets received, as determined by the number
        of UART "start" bits processed.

        '''
        return super(ZMQ_IO, self).get_packet_count(io_channel=io_channel, address=self._address)

    def ping(self):
        '''
        Send a ping to the system and return True if the first two bytes
        of the response are b'OK'.

        '''
        return super(ZMQ_IO, self).ping(addresses=[self._address])[self._address]
