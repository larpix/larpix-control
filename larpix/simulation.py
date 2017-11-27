'''
Simulate the LArPix chip's behavior.

'''
from __future__ import absolute_import

import larpix.larpix as larpix
import time
from collections import deque

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
        if isinstance(self.next, MockLArPix):
            receive_fn = self.next.receive
        elif isinstance(self.next, MockFormatter):
            receive_fn = self.next.receive_miso
        return receive_fn(packet)

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

class MockSerial(object):
    '''
    A mock serial interface to connect ``larpix.larpix.Controller`` to
    ``MockLArPix``.

    '''
    def __init__(self, port=None, baudrate=9600, timeout=None):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.formatter = None

    def __call__(self, *args, **kwargs):
        return self

    def write(self, data):
        self.formatter.receive_mosi(data)

    def read(self, nbytes):
        return self.formatter.send_miso(nbytes)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

class MockFormatter(object):
    '''
    A mock data formatter (i.e. FPGA) to convert serial data into
    ``larpix.larpix.Packet``s for ``MockLArPix`` consumption.

    '''
    def __init__(self):
        self.chips = []
        self.mosi_destination = None
        self.miso_source = None
        self.miso_buffer = deque()
        ''' Represents all buffers between the FPGA and the serial port.'''
        self._controller = larpix.Controller(None)
        '''Used for its parse_input function.'''

    def receive_mosi(self, data):
        '''
        Format bytestream data into Packets, and send it on to the daisy
        chain.

        Note: there is no internal buffer for MOSI data, as per the FPGA
        spec. This is entirely due to the fact that the RS-232 baudrate
        is 1Mbaud and the LArPix bitrate is 10MHz, i.e. much faster.

        '''
        packets = self._controller.parse_input(data)
        self.send_mosi(packets)

    def receive_miso(self, packet):
        '''
        Store the received packets in the internal buffer.

        '''
        self.miso_buffer.append(packet)
        return packet

    def send_mosi(self, packets):
        '''
        Send the given packets into the daisy chain.

        '''
        for packet in packets:
            self.mosi_destination.receive(packet)

    def send_miso(self, nbytes):
        '''
        Return a bytestream of length nbytes created from the packets in
        the MISO buffer.

        Note: if nbytes doesn't line up with the end of a packet, the
        packet will be split and the part that is not sent out will be
        discarded. This is **different behavior** compared to the FPGA
        setup currently in use.

        '''
        bytestream = b''
        while len(bytestream) < nbytes and self.miso_buffer:
            packet_bytes = self.miso_buffer.popleft().bytes()
            new_bytes = b's' + packet_bytes + b'\x00' + b'q'
            num_to_append = min(len(new_bytes),
                    nbytes - len(bytestream))
            bytestream += new_bytes[:num_to_append]
        return bytestream