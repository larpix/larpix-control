'''
Simulate the LArPix chip's behavior.

'''
from __future__ import absolute_import

import larpix.larpix as larpix
import time

class MockLArPix(object):
    '''
    A mock/simulation LArPix chip that can interface with the
    ``larpix.larpix`` module.

    '''
    def __init__(self, chip_id, io_chain):
        self.chip_id = chip_id
        self.io_chain = io_chain
        self.previous = None
        self.next = None
        self.config = larpix.Configuration()
        self.vref = 1.5
        self.vcm = 0.2
        self.adc_bins = 256
        self.adc_lsb = (self.vref - self.vcm)/self.adc_bins

    def receive(self, packet):
        '''
        Handle the packet by either processing it or sending it on.

        '''
        if packet.chipid != self.chip_id:
            return self.send(packet)
        if packet.packet_type == packet.CONFIG_READ_PACKET:
            output = larpix.Packet()
            output.packet_type = packet.CONFIG_READ_PACKET
            output.chipid = self.chip_id
            output.register_address = packet.register_address
            output.register_data = self.config.all_data()[
                    packet.register_address]
            output.assign_parity()
            return self.send(output)
        elif packet.packet_type == packet.CONFIG_WRITE_PACKET:
            update = {packet.register_address: packet.register_data}
            self.config.from_dict_registers(update)
            return None
        else:
            return self.send(packet)

    def send(self, packet):
        '''
        Emit and return the given packet.

        '''
        if self.next is None:
            print(repr(packet))
            return packet
        else:
            return self.next.receive(packet)

    def trigger(self, n_electrons, channel):
        '''
        Trigger the chip for charge readout.

        '''
        if self.config.csa_gain == 0:
            gain_uV_e = 45
        elif self.config.csa_gain == 1:
            gain_uV_e = 4
        V_per_uV = 1e-6
        voltage = n_electrons * gain_uV_e * V_per_uV
        adcs = self.digitize(voltage)
        packet = larpix.Packet()
        packet.packet_type = packet.DATA_PACKET
        packet.chipid = self.chip_id
        packet.channel_id = channel
        packet.timestamp = self.timestamp()
        packet.dataword = adcs
        packet.assign_parity()
        return self.send(packet)

    def timestamp(self):
        '''
        Return a timestamp for this chip that makes sense.

        '''
        return int(time.time()//100)

    def digitize(self, voltage):
        '''
        Convert the given voltage into ADC counts.

        '''
        numerator = (voltage - self.vcm) * self.adc_bins
        denominator = self.vref - self.vcm
        ratio = int(numerator//denominator)
        ratio = max(0, ratio)
        ratio = min(self.adc_bins-1, ratio)
        return ratio
