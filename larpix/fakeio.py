'''
A module for the FakeIO class.

'''
from __future__ import print_function
from collections import deque

class FakeIO(object):
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
        self.is_listening = False
        self.queue = deque()

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
        self.is_listening = True

    def stop_listening(self):
        '''
        Mock-up of no longer listening for new packets.

        '''
        self.is_listening = False

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

