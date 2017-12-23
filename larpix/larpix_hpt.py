from __future__ import absolute_import

from math import fmod

def get_ns(time_in_sec):
    return int(fmod(time_in_sec * 1e9, 1e9))

def get_s(time_in_sec):
    return int(time_in_sec)

class larpix_hpt(object):
    '''Class for precision time'''
    larpix_clk_freq = 5e6 #Hz
    larpix_offset_d = 2**24 #clk cycles
    offset = {}
    ref_time = None
    prev_time = {}

    def __init__(self, s=0, ns=0, cpu_time=0, adc_time=0):
        '''Constructor'''
        self.s = int(s)
        self.ns = int(fmod(ns,1e9))
        self.cpu_time = cpu_time
        self.adc_time = int(adc_time)

    def __str__(self):
        string = 's: %d' % self.s
        string += ' ns: %d' % self.ns
        string += ' cpu_time: %f' % self.cpu_time
        string += ' adc_time: %d' % self.adc_time
        return string

    def __repr__(self):
        return str(self)

    def __eq__(self, hpt):
        return self.s == hpt.s and self.ns == hpt.ns

    def __gt__(self, hpt):
        if self.s > hpt.s:
            return True
        elif self.s == hpt.s:
            return self.ns > hpt.ns
        else:
            return False

    def __lt__(self, hpt):
        return not (self > hpt) and not (self == hpt)

    def __add__(self, hpt):
        sum_ns = int(fmod(self.ns + hpt.ns, 1e9))
        sum_s = self.s + hpt.s + int((self.ns + hpt.ns) / 1e9)
        sum_cpu = self.cpu_time + hpt.cpu_time
        sum_adc = self.adc_time + hpt.adc_time
        return larpix_hpt(sum_s, sum_ns, sum_cpu, sum_adc)

    def __sub__(self, hpt):
        delta_ns = int(fmod(self.ns - hpt.ns, 1e9))
        delta_s = self.s - hpt.s + int((self.ns - hpt.ns) / 1e9)
        delta_cpu = self.cpu_time - hpt.cpu_time
        delta_adc = self.adc_time - hpt.adc_time
        return larpix_hpt(delta_s, delta_ns, delta_cpu, delta_adc)

    def __float__(self):
        return float(self.s + self.ns / 1e9)

    @staticmethod
    def from_packet(cpu_time=0, packet=None):
        '''Constructor from packet'''
        if packet is None:
            adc_time = 0
            chip_id = 0
        else:
            adc_time = packet.timestamp
            chip_id = packet.chipid
        return larpix_hpt.serialized_hpt(cpu_time, adc_time, chip_id)

    @staticmethod
    def serialized_hpt(cpu_time=0, adc_time=0, chip_id=0):
        '''Generates next serialized packet from cpu time and adc time'''
        if not chip_id in larpix_hpt.offset:
            larpix_hpt.offset[chip_id] = 0
        adj_adc_time = adc_time + larpix_hpt.offset[chip_id]
        if not chip_id in larpix_hpt.prev_time:
            pass
        elif cpu_time == larpix_hpt.prev_time[chip_id].cpu_time:
            # same serial read but adc time has rolled over
            n_offset = 0
            while adc_time + n_offset*larpix_hpt.larpix_offset_d < larpix_hpt.prev_time[chip_id].adc_time:
                n_offset += 1
                larpix_hpt.offset[chip_id] += larpix_hpt.larpix_offset_d
                adj_adc_time += larpix_hpt.larpix_offset_d
        else:
            # new serial read
            n_offset = int(((cpu_time - larpix_hpt.prev_time[chip_id].cpu_time)*larpix_hpt.larpix_clk_freq)/larpix_hpt.larpix_offset_d)
            larpix_hpt.offset[chip_id] += larpix_hpt.larpix_offset_d * n_offset
            adj_adc_time += larpix_hpt.larpix_offset_d * n_offset
            if adc_time < larpix_hpt.prev_time[chip_id].adc_time:
                # one extra rollover occurred
                adj_adc_time += larpix_hpt.larpix_offset_d
                larpix_hpt.offset[chip_id] += larpix_hpt.larpix_offset_d

        hpt = larpix_hpt()
        if larpix_hpt.ref_time is None:
            hpt.s = get_s(adj_adc_time/larpix_hpt.larpix_clk_freq + cpu_time)
            hpt.ns = get_ns(adj_adc_time/larpix_hpt.larpix_clk_freq + cpu_time)
        else:
            hpt.ns = get_ns(adj_adc_time/larpix_hpt.larpix_clk_freq)
            hpt.s = get_s(adj_adc_time/larpix_hpt.larpix_clk_freq)
            hpt = hpt + larpix_hpt.ref_time

        hpt.cpu_time = cpu_time
        hpt.adc_time = adc_time
        # update stored times
        larpix_hpt.set_prev_time(chip_id, hpt)
        if larpix_hpt.ref_time is None:
            larpix_hpt.set_ref_time(hpt)
        return hpt

    @staticmethod
    def set_ref_time(ref_hpt):
        larpix_hpt.ref_time = ref_hpt

    @staticmethod
    def set_prev_time(chip_id, prev_hpt):
        larpix_hpt.prev_time[chip_id] = prev_hpt
    
    @staticmethod
    def reset():
        larpix_hpt.offset = {}
        larpix_hpt.ref_time = None
        larpix_hpt.prev_time = {}

