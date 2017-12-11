'''
A module to assist loading serial data logs for debugging
'''
from __future__ import absolute_import

from datetime import datetime
from larpix.dataloader import DataLoader
from larpix.larpix import Controller

class LogAnalyzer(DataLoader):
    '''Analyzer of LArPix serial log transmissions'''

    def next_transmission(self):
        '''Parse next set of packets in controller transmission log'''
        block_desc = self.next_block()
        if block_desc is None:
            return None
        if block_desc['block_type'] == 'data':
            packets = Controller.parse_input(bytes(block_desc['data']))
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

