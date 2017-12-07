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

