from .key import Key
from .configuration import Configuration_v1, Configuration_v2, Configuration_Lightpix_v1
from .packet import Packet_v1, Packet_v2

class Chip(object):
    '''
    Represents one LArPix chip and helps with configuration and packet
    generation.

    '''

    def __init__(self, chip_key, version=2):
        '''
        Create a new Chip object with the given ``chip_key``. See the ``Key``
        class for the key specification. Key can be specified by a valid keystring
        or a ``Key`` object.

        '''
        self.asic_version = version
        if self.asic_version == 1:
            self.config = Configuration_v1()
        elif self.asic_version == 2:
            self.config = Configuration_v2()
        elif self.asic_version == 'lightpix-v1.0':
            self.config = Configuration_Lightpix_v1()
        else:
            raise RuntimeError('chip asic version is invalid')
        chip_key = Key(chip_key)
        self.io_group = chip_key.io_group
        self.io_channel = chip_key.io_channel
        self.chip_id = chip_key.chip_id
        self.reads = []
        self.new_reads_index = 0

    def __str__(self):
        return 'Chip (key: {}, version: {})'.format(str(self.chip_key), self.asic_version)

    def __repr__(self):
        return 'Chip(chip_key={}, version={})'.format(str(self.chip_key), self.asic_version)

    @property
    def chip_key(self):
        return Key(self.io_group, self.io_channel, self.chip_id)

    @chip_key.setter
    def chip_key(self, val):
        val = Key(val)
        self.io_group = val.io_group
        self.io_channel = val.io_channel
        self.chip_id = val.chip_id

    def is_chip_id_set(self):
        '''
        Check if chip id (as specified by unique key) matches the chip id stored
        in the configuration.
        Only valid for v2 asics, if v1 asic, will always return ``True``
        Note: Even if this function returns True, it's possible the chip ID has not been sent from the larpix-control software onto the ASIC hardware

        '''
        if self.asic_version == 1:
            return True
        elif self.asic_version in (2, 'lightpix-v1.0'):
            return self.config.chip_id == self.chip_id

    def get_configuration_packets(self, packet_type, registers=None):
        '''
        Return a list of Packet objects to read or write (depending on
        ``packet_type``) the specified configuration registers (or all
        registers by default).

        '''
        conf = self.config
        if registers is None:
            registers = range(conf.num_registers)
        packets = []
        packet_register_data = conf.all_data()
        for i, data in enumerate(packet_register_data):
            if i not in registers:
                continue
            if self.asic_version == 1:
                packet = Packet_v1()
            else:
                packet = Packet_v2()
            packet.packet_type = packet_type
            packet.chip_id = self.chip_id
            packet.chip_key = self.chip_key
            packet.register_address = i
            if packet_type == packet.CONFIG_WRITE_PACKET:
                packet.register_data = data
            elif packet_type == packet.CONFIG_READ_PACKET:
                packet.register_data = 0
            else:
                raise ValueError('incorrect packet_type for configuration packets')
            packet.assign_parity()
            packets.append(packet)
        return packets

    def get_configuration_write_packets(self, registers=None):
        '''
        Return a list of Packet objects to write corresponding to the specified
        configuration registers (all by default)

        '''
        if self.asic_version == 1:
            return self.get_configuration_packets(Packet_v1.CONFIG_WRITE_PACKET, registers)
        return self.get_configuration_packets(Packet_v2.CONFIG_WRITE_PACKET, registers)

    def get_configuration_read_packets(self, registers=None):
        '''
        Return a list of Packet objects to write corresponding to the specified
        configuration registers (all by default)

        '''
        if self.asic_version == 1:
            return self.get_configuration_packets(Packet_v1.CONFIG_READ_PACKET, registers)
        return self.get_configuration_packets(Packet_v2.CONFIG_READ_PACKET, registers)

    def sync_configuration(self, index=-1):
        '''
        Adjust self.config to match whatever config read packets are in
        self.reads[index].

        Defaults to the most recently read PacketCollection. Later
        packets in the list will overwrite earlier packets. The
        ``index`` parameter could be a slice.

        '''
        updates = {}
        if isinstance(index, slice):
            for collection in self.reads[index]:
                for packet in collection:
                    if packet.packet_type == packet.CONFIG_READ_PACKET:
                        updates[packet.register_address] = packet.register_data
        else:
            for packet in self.reads[index]:
                if packet.packet_type == packet.CONFIG_READ_PACKET:
                    updates[packet.register_address] = packet.register_data
        if self.asic_version == 1:
            self.config.from_dict_registers(updates)
        else:
            self.config.from_dict_registers(updates, endian=Packet_v2.endian)

    def export_reads(self, only_new_reads=True):
        '''
        Return a dict of the packets this Chip has received.

        If ``only_new_reads`` is ``True`` (default), then only the
        packets since the last time this method was called will be in
        the dict. Otherwise, all of the packets stored in ``self.reads``
        will be in the dict.

        '''
        data = {}
        data['chip_key'] = self.chip_key
        data['chip_id'] = self.chip_id
        if only_new_reads:
            packets = self.reads[self.new_reads_index:]
        else:
            packets = self.reads
        data['packets'] = list(map(lambda x:x.export(), packets))
        self.new_reads_index = len(self.reads)
        return data
