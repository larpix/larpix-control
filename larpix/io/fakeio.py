'''
A module for the FakeIO class.

'''
from __future__ import print_function
from collections import deque

from larpix.io import IO

class FakeIO(IO):
    '''
    An IO stand-in that sends output to stdout (i.e. print) and reads
    input from a data member that can be set in advance.

    The queue is implemented as a ``collections.deque`` object. Data can
    be queued up in advance through repeated calls to
    ``queue.append()``. The first element of the queue will be passed on to
    the ``Controller.read`` method each time it is called. This is a
    true queue, i.e. first-in, first-out.

    The format for an element of the queue is a tuple:
    ``([list_of_Packets], b'corresponding bytes')``.

    Although meaningless in terms of the internal implementation,
    ``FakeIO`` objects contain an internal state determining whether the
    object is currently "listening," and will raise a ``RuntimeError``
    if ``empty_queue`` is called when the object is not listening.

    '''
    def __init__(self):
        super(FakeIO, self).__init__()
        self.queue = deque()

    @classmethod
    def encode(cls, packets):
        '''
        Placeholder for packet encoding

        :returns: ``packets``
        '''
        return packets

    @classmethod
    def decode(cls, msgs):
        '''
        Placeholder for message decoding

        :returns: ``msgs``
        '''
        return msgs

    @classmethod
    def is_valid_chip_key(cls, key):
        return super(cls, cls).is_valid_chip_key(key)

    @classmethod
    def parse_chip_key(cls, key):
        '''
        Placeholder function for parsing chip keys ``chip_key``

        :param key: chip key to be returned ``in dict``

        :returns: ``dict`` with keys ``('chip_key')``

        '''
        return_dict = super(cls, cls).parse_chip_key(key)
        return_dict['chip_key'] = key
        return return_dict

    @classmethod
    def generate_chip_key(cls, **kwargs):
        '''
        Placeholder function for generating a chip key

        :param chip_key: chip key to return

        :returns: ``chip_key`` that was passed into the function

        '''
        if not 'chip_key' in kwargs:
            raise ValueError('FakeIO chip keys require an explicit chip_key')
        return kwargs['chip_key']

    def send(self, packets):
        '''
        Print the packets to stdout.

        '''
        for packet in packets:
            print(packet)

    def start_listening(self):
        '''
        Mock-up of beginning to listen for new packets.

        '''
        super(FakeIO, self).start_listening()

    def stop_listening(self):
        '''
        Mock-up of no longer listening for new packets.

        '''
        super(FakeIO, self).stop_listening()

    def empty_queue(self):
        '''
        Read and remove the next item from the internal queue and return
        it as if it were data that had just been read.

        '''
        if not self.is_listening:
            raise RuntimeError('Cannot empty queue when not'
                    ' listening')
        data = self.queue.popleft()
        return data

