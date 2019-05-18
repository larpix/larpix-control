'''
A module to assist loading serial data logs for debugging
'''
from __future__ import absolute_import
from datetime import datetime
from math import sqrt

from .dataloader import DataLoader
from ..larpix import Controller
from ..larpix import Packet

class LogAnalyzer(DataLoader):
    '''Analyzer of LArPix serial log transmissions'''
    def __init__(self, filename=None):
        '''Constructor'''
        DataLoader.__init__(self, filename)
        # Merge packets split across transmissions?
        self._stitch_transmissions = False
        self._unused_bytes = bytes()

    def next_transmission(self):
        '''Parse next set of packets in controller transmission log'''
        block_desc = self.next_block()
        if block_desc is None:
            return None
        if block_desc['block_type'] == 'data':
            parse_bytes = bytes()
            if self._stitch_transmissions and len(self._unused_bytes)>0:
                # Use leftover bytes from previous transmission
                parse_bytes += self._unused_bytes
                self._unused_bytes = bytes()
            # Get bytes from this transmission
            parse_bytes += bytes(block_desc['data'])
            if self._stitch_transmissions:
                # Remove extra bytes for use in next transmission
                #   FIXME: assumes all packets are 10 bytes in length!
                n_extra_bytes = (len(parse_bytes) % 10)
                if n_extra_bytes != 0:
                    self._unused_bytes = parse_bytes[-n_extra_bytes:]
                    parse_bytes = parse_bytes[:-n_extra_bytes]
            packets = Controller.parse_input(parse_bytes)
            block_desc['packets'] = packets
        return block_desc

    def dump_log(self):
        '''Dump entire log to terminal'''
        while True:
            next_trans = self.next_transmission()
            if next_trans is None:
                break
            self.print_transmission(next_trans)
        return

    def check_parity(self, transmission):
        '''Check parities of all packets in transmission'''
        npackets_bad_parity = 0
        if transmission['block_type'] != 'data': return 0
        return sum(1 for pack in transmission['packets']
                   if not pack.has_valid_parity())

    def check_fifo(self, transmission):
        '''Returns tuple of number of half full fifos and full fifos in transmission'''
        half_flags = 0
        full_flags = 0
        if transmission['block_type'] != 'data': return (0,0)
        for packet in transmission['packets']:
            if packet.packet_type == Packet.DATA_PACKET:
                half_flags += int(packet.fifo_half_flag)
                full_flags += int(packet.fifo_full_flag)
        return (half_flags, full_flags)

    def adc_report(self, interval_step=100000, max_read=None, return_list=False):
        '''
        Print min, max, avg channel adcs for all packets with good parity in log
        Returns list of adc values for each channel if ``fast=False``
        Channel id is ``chip_id * 32 + channel``
        '''
        print('========= ADC Report ========================')
        npackets_total = 0
        npackets_bad_parity_total = 0
        npackets_good_total = {}
        adc_min_total = {}
        adc_max_total = {}
        adc_avg_total = {}
        adc_ssq_total = {} # sum of squares
        adc_total = {}
        npackets_interval = 0
        npackets_bad_parity_interval = 0
        npackets_good_interval = {}
        adc_min_interval = {}
        adc_max_interval = {}
        adc_avg_interval = {}
        adc_ssq_interval = {}
        while True:
            next_trans = self.next_transmission()
            if next_trans is None:
                break
            if next_trans['block_type'] != 'data': continue
            if next_trans['data_type'] != 'read': continue
            if len(next_trans['packets']) <= 0: continue
            npackets_total += len(next_trans['packets'])
            npackets_interval += len(next_trans['packets'])
            for packet in next_trans['packets']:
                if packet.packet_type != Packet.DATA_PACKET:
                    continue
                adc = packet.dataword
                chipid = packet.chipid
                channel = packet.channel_id
                channelid = chipid * 32 + channel
                # Remove packets with bad parity
                if packet.has_valid_parity() is False:
                    npackets_bad_parity_total += 1
                    npackets_bad_parity_interval += 1
                    continue
                # Store adc info for good packets
                if not channelid in npackets_good_total:
                    npackets_good_total[channelid] = 1
                    adc_max_total[channelid] = adc
                    adc_min_total[channelid] = adc
                    adc_avg_total[channelid] = adc
                    adc_ssq_total[channelid] = adc * adc
                    adc_total[channelid] = [adc]
                else:
                    npackets_good_total[channelid] += 1
                    adc_max_total[channelid] = max(adc, adc_max_total[channelid])
                    adc_min_total[channelid] = min(adc, adc_min_total[channelid])
                    adc_avg_total[channelid] += float(adc - adc_avg_total[channelid])/npackets_good_total[channelid] # running avg
                    adc_ssq_total[channelid] += adc * adc
                    adc_total[channelid].append(adc)
                if not channelid in npackets_good_interval:
                    npackets_good_interval[channelid] = 1
                    adc_max_interval[channelid] = adc
                    adc_min_interval[channelid] = adc
                    adc_avg_interval[channelid] = adc
                    adc_ssq_interval[channelid] = adc * adc
                else:
                    npackets_good_interval[channelid] += 1
                    adc_max_interval[channelid] = max(adc, adc_max_interval[channelid])
                    adc_min_interval[channelid] = min(adc, adc_min_interval[channelid])
                    adc_avg_interval[channelid] += float(adc - adc_avg_interval[channelid])/npackets_good_interval[channelid] # running avg
                    adc_ssq_interval[channelid] += adc * adc
            if not max_read is None and npackets_total > max_read:
                # Stop at max
                break
            if npackets_interval > interval_step:
                # Interval Report
                print('  N_packets, N_badparity: %d %d' % (
                    npackets_interval,
                    npackets_bad_parity_interval))
                print('  Chip, Channel, Good packets, Min ADC, Max ADC, Avg ADC, Std Dev ADC')
                for channelid in npackets_good_interval.keys():
                    print('  %4d, %7d, %12d, %7d, %7d, %7.2f, %11.2f' % (
                            channelid // 32,
                            channelid % 32,
                            npackets_good_interval[channelid],
                            adc_min_interval[channelid],
                            adc_max_interval[channelid],
                            adc_avg_interval[channelid],
                            sqrt(float(adc_ssq_interval[channelid])/npackets_good_interval[channelid] - adc_avg_interval[channelid]**2)))
                    del npackets_good_interval[channelid]
                    del adc_min_interval[channelid]
                    del adc_max_interval[channelid]
                    del adc_avg_interval[channelid]
                    del adc_ssq_interval[channelid]
                npackets_interval = 0
                npackets_bad_parity_interval = 0
        # Total Report
        print('== Summary of ADC values ==')
        print('  Total number of packets: %d' % npackets_total)
        print('  Packets with bad parity: %d' % npackets_bad_parity_total)
        print('  Channel breakdown:')
        print('  Chip, Channel, Good packets, Min ADC, Max ADC, Avg ADC, Std Dev ADC')
        mean_std_dev = 0
        n = 0
        for channelid in sorted(npackets_good_total.keys()):
            print('  %4d, %7d, %12d, %7d, %7d, %7.2f, %11.2f' % (
                    channelid // 32,
                    channelid % 32,
                    npackets_good_total[channelid],
                    adc_min_total[channelid],
                    adc_max_total[channelid],
                    adc_avg_total[channelid],
                    sqrt(float(adc_ssq_total[channelid])/npackets_good_total[channelid] - adc_avg_total[channelid]**2)))
        if return_list:
            return adc_total

    def parity_report(self, interval_step=100000):
        '''Check parities of all packets in log, and report status'''
        print('========= Parity Report =====================')
        npackets_total = 0
        npackets_bad_parity_total = 0
        npackets_interval = 0
        npackets_bad_parity_interval = 0
        while True:
            next_trans = self.next_transmission()
            if next_trans is None:
                break
            if next_trans['block_type'] != 'data': continue
            if next_trans['data_type'] != 'read': continue
            if len(next_trans['packets']) <= 0: continue
            npackets_bad_parity = self.check_parity(next_trans)
            npackets_total += len(next_trans['packets'])
            npackets_bad_parity_total += npackets_bad_parity
            npackets_interval += len(next_trans['packets'])
            npackets_bad_parity_interval += npackets_bad_parity
            if npackets_interval > interval_step:
                # Interval Report
                print('  N_packets, N_badparity, Bad Fraction: %d %d %f' % (
                    npackets_interval,
                    npackets_bad_parity_interval,
                    npackets_bad_parity_interval/float(npackets_interval)))
                npackets_interval = 0
                npackets_bad_parity_interval = 0
        # Total Report
        print('== Summary of Parity Check ==')
        print('  Total number of packets: %d' % npackets_total)
        print('  Packets with bad parity: %d' % npackets_bad_parity_total)
        if npackets_total > 0:
            print('                 Fraction: %f' % (npackets_bad_parity_total/
                                                     float(npackets_total)))
        return

    def fifo_report(self, interval_step=100000):
        '''Check fifo flags of all packets in log, and report status'''
        print('========= FIFO Report =====================')
        npackets_total = 0
        npackets_half_fifo_total = 0
        npackets_full_fifo_total = 0
        npackets_interval = 0
        npackets_half_fifo_interval = 0
        npackets_full_fifo_interval = 0
        while True:
            next_trans = self.next_transmission()
            if next_trans is None:
                break
            if next_trans['block_type'] != 'data': continue
            if next_trans['data_type'] != 'read': continue
            if len(next_trans['packets']) <= 0: continue
            n_half, n_full = self.check_fifo(next_trans)
            npackets_total += len(next_trans['packets'])
            npackets_half_fifo_total += n_half
            npackets_full_fifo_total += n_full
            npackets_interval += len(next_trans['packets'])
            npackets_half_fifo_interval += n_half
            npackets_full_fifo_interval += n_full
            if npackets_interval > interval_step:
                # Interval Report
                print('  N_packets, N_half, N_full: %d %d %d' % (
                    npackets_interval,
                    npackets_half_fifo_interval,
                    npackets_full_fifo_interval))
                npackets_interval = 0
                npackets_half_fifo_interval = 0
                npackets_full_fifo_interval = 0
        # Total Report
        print('== Summary of FIFO Check ==')
        print('  Total number of packets: %d' % npackets_total)
        print('  Packets with half full FIFO: %d' % npackets_half_fifo_total)
        print('  Packets with full FIFO: %d' % npackets_full_fifo_total)
        return

    @classmethod
    def print_transmission(cls, block, show_packets=True):
        '''Print transmission to terminal'''
        tfmt = '%Y-%m-%d %H:%M:%S.%f'
        print('%%%%%%%%%%%%%%%% Next Block %%%%%%%%%%%%%%%%')
        print(' Block Type: %s' % block['block_type'])
        if block['block_type']=='file':
            print('  Data version: %d.%d' % (block['major_version'],
                                             block['minor_version']))
            utc_dt = datetime.utcfromtimestamp(block['starttime'])
            loc_dt = datetime.fromtimestamp(block['starttime'])
            print('  Time, UTC:    %s' % utc_dt.strftime(tfmt))
            print('     (Local):  (%s)' % loc_dt.strftime(tfmt))
        if block['block_type']=='data':
            print('  Data type:    %s' % block['data_type'])
            utc_dt = datetime.utcfromtimestamp(block['time'])
            loc_dt = datetime.fromtimestamp(block['time'])
            print('  Time, UTC:    %s' % utc_dt.strftime(tfmt))
            print('     (Local):  (%s)' % loc_dt.strftime(tfmt))
            print('  Size [bytes]: %d' % len(block['data']))
            print('  N(packets):   %d' % len(block['packets']))
            if show_packets and (len(block['packets']) > 0):
                print('  Packets:')
                for packet in block['packets']:
                    print('   %s' % str(packet))
        return

