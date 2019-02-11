from __future__ import absolute_import
from functools import total_ordering
import sys
from math import fmod

__all__ = ['Timestamp']

if sys.version_info > (3,):
    long = int
    __all__ += ['long']

@total_ordering
class Timestamp(object):
    '''Class for precision time'''
    larpix_clk_freq = long(5e6) #Hz
    larpix_offset_d = long(2**24) #clk cycles

    def __init__(self, ns=0, cpu_time=0, adc_time=0, adj_adc_time=0):
        '''
        Constructor

        Keyword arguments:
        ``ns`` - the serialized timestamp in ns (time since epoch)
        ``cpu_time`` - the serial timestamp used to create ns and adj_adc_time (time since
        epoch)
                - float (expected source is a call to ``time.time()``)
                - must be accurate to at least ``larpix_offset_d/larpix_clk_freq``
        ``adc_time`` - the chip timestamp used to create ``ns`` and ``adj_adc_time`` (clk
        cycles since last rollover)
                - sets the precision of ``Timestamp`` (``1/larpix_clk_freq``)
                - ``int`` between ``0`` and ``larpix_offset_d-1``
        ``adj_adc_time`` - the chip timestamp incremented to account for rollovers (i.e. a
        clk cycle counter)
        '''
        self.ns = long(ns)
        self.cpu_time = float(cpu_time)
        if adc_time // Timestamp.larpix_offset_d != 0:
            raise ValueError('adc_time is out of bounds')
        self.adc_time = int(adc_time)
        self.adj_adc_time = long(adj_adc_time)

    def __str__(self):
        string = 'Timestamp('
        string += 'ns=%d, ' % self.ns
        string += 'cpu_time=%f, ' % self.cpu_time
        string += 'adc_time=%d, ' % self.adc_time
        string += 'adj_adc_time=%d' % self.adj_adc_time
        string += ')'
        return string

    def __repr__(self):
        return str(self)

    def __eq__(self, timestamp):
        '''
        Equality compares only timestamp ns (presumably one only cares about the time
        represented by the Timestamp instance - not how it was calculated).
        '''
        return self.ns == timestamp.ns

    def __gt__(self, timestamp):
        '''
        Ordering is determined only by timestamp ns - see ``__eq__`` note.
        '''
        return self.ns > timestamp.ns

    def __add__(self, timestamp):
        '''
        Sum ns, cpu_time, adc_time, and adj_adc_time of each timestamp.
        Resulting adc_time is mod larpix_offset_d
        '''
        sum_ns = self.ns + timestamp.ns
        sum_cpu = self.cpu_time + timestamp.cpu_time
        sum_adc = int(fmod(self.adc_time + timestamp.adc_time, Timestamp.larpix_offset_d))
        sum_adj_adc = self.adj_adc_time + timestamp.adj_adc_time
        return Timestamp(sum_ns, sum_cpu, sum_adc, sum_adj_adc)

    def __sub__(self, timestamp):
        '''
        Return the difference of ns, cpu_time, adc_time, and adj_adc_time of each timestamp.
        Resulting adc_time is mod larpix_offset_d
        '''
        delta_ns = self.ns - timestamp.ns
        delta_cpu = self.cpu_time - timestamp.cpu_time
        delta_adc = int(fmod(self.adc_time - timestamp.adc_time, Timestamp.larpix_offset_d))
        delta_adj_adc = self.adj_adc_time - timestamp.adj_adc_time
        return Timestamp(delta_ns, delta_cpu, delta_adc, delta_adj_adc)

    def __float__(self):
        '''
        Return a float of sec since epoch
        Note: this is very likely to cause a loss of precision
        '''
        return float(self.ns / 1e9)

    @staticmethod
    def from_packet(packet, cpu_time, ref_time=None):
        '''
        Constructor from packet
        Note: a reference time is required in order to gain precision greater than the cpu
        timestamp, if no reference is provided ns == cpu_time * 1e9 (see description of
        serialized_timestamp() for more details)

        Example usage:
        Generate a list of timestamps from two aligned lists of packets and serial read
        times from a single chip
        ``
        list_of_timestamps = []
        ref_time = from_packet(packets[0], serial_read_time[0])
        for i,packet in enumerate(packets):
            list_of_timestamps += [from_packet(packet, serial_read_time[i], ref_time]
            ref_time = list_of_timestamps[-1]
        ``
        '''
        return Timestamp.serialized_timestamp(adc_time=packet.timestamp, cpu_time=cpu_time,
                                              ref_time=ref_time)

    @staticmethod
    def serialized_timestamp(adc_time, cpu_time, ref_time=None):
        '''
        Generate next serialized packet timestamp from cpu time, adc time, and a reference
        timestamp.

        The algorithm is as follows:
        - If no reference packet, don't add any rollovers (``adj_adc_time == adc_time`` and
        ``ns == cpu_time * 1e9``)
        - If reference packet has the same ``cpu_time``, add rollovers to ``adj_adc_time``
        until ``ref_time.adj_adc_time < adj_adc_time``
        - If reference packet has a different ``cpu_time``, estimate the number of clk cycles
        that have occurred between serial reads add rollovers to ``adj_adc_time`` until the
        difference between ``ref_time.adj_adc_time`` and ``adj_adc_time`` is less than
        ``larpix_offset_d/2`` away from the estimated number of clk cycles
        - The previous two steps provide an ``adj_adc_time`` that is serialized, calculate
        ``ns`` from ``ref_time.ns + <diff btw adj_adc_times>/larpix_clk_freq``

        In order to guarantee that the timestamps are serialized:
        - within a single serial read, the data rate must be greater than
        ``larpix_clk_freq/larpix_offset_d`` (nominally ~.3Hz) OR the serial timeout must be
        less than ``larpix_offset_d/larpix_clk_freq`` (nominally ~3s)
        - between serial reads, the first data packet should arrive within
        ``larpix_offset_d/larpix_clk_freq/2`` of the serial read time (~1.5s)
        - reference time should be the timestamp of the previously read packet from
        that chip (there is a delay between packet creation and packet receipt that can
        interfere with the time ordering of packets between chips)
        - reference time must be a properly sychronized timestamp that was recieved
                - if in the same serial read: within 1 rollover before the current
                timestamp
                - if in separate serial reads: from a previous serial read
        '''
        adj_adc_time = long(adc_time)
        if ref_time is None:
            pass
        elif cpu_time == ref_time.cpu_time:
            # same serial read but adc time may have rolled over
            while adj_adc_time < ref_time.adj_adc_time:
                adj_adc_time += Timestamp.larpix_offset_d
        else:
            # new serial read
            # estimate number of clk cycles between reads
            n_clk_cycles = long((cpu_time - ref_time.ns * 1e-9) * Timestamp.larpix_clk_freq)
            # add offsets until you are close to the predicted number of clk cycles
            while adj_adc_time - ref_time.adj_adc_time - n_clk_cycles \
                    < -Timestamp.larpix_offset_d / 2:
                adj_adc_time += Timestamp.larpix_offset_d

        timestamp = None
        if ref_time is None:
            timestamp = Timestamp(cpu_time * 1e9, cpu_time, adc_time, adj_adc_time)
        else:
            ns = ref_time.ns + long((adj_adc_time - ref_time.adj_adc_time) * long(1e9) \
                                        / Timestamp.larpix_clk_freq)
            timestamp = Timestamp(ns, cpu_time, adc_time, adj_adc_time)
        return timestamp
