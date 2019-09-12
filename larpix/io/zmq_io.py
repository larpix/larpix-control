import time
import zmq
import sys
import copy
import warnings

from larpix.io import MultiZMQ_IO
from larpix import Packet, Key

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
    _valid_config_classes = MultiZMQ_IO._valid_config_classes + ['ZMQ_IO']

    def __init__(self, config_filepath=None, **kwargs):
        super(ZMQ_IO, self).__init__(config_filepath=config_filepath, **kwargs)
        self._address = list(self._io_group_table.values())[0]

    def load(self, filepath=None):
        super(ZMQ_IO, self).load(filepath)
        if len(self._io_group_table.inv) != 1:
            raise RuntimeError('multiple adresses found in configuration - use '
                'MultiZMQ_IO if you\'d like to connect to multiple systems')

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

    def decode(self, msgs, **kwargs):
        '''
        Convert a list ZMQ messages into packets

        '''
        if not 'address' in kwargs:
            return super(ZMQ_IO, self).decode(msgs, address=self._address, **kwargs)
        return super(ZMQ_IO, self).decode(msgs, **kwargs)

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
