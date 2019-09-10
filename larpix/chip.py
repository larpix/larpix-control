from .key import Key
from .configuration import Configuration
from .packet import Packet

class Chip(object):
    '''
    Represents one LArPix chip and helps with configuration and packet
    generation.

    '''
    num_channels = 32
    def __init__(self, chip_key):
        '''
        Create a new Chip object with the given ``chip_key``. See the ``Key``
        class for the key specification. Key can be specified by a valid keystring
        or a ``Key`` object.

        '''
        self.chip_key = Key(chip_key)
        self.data_to_send = []
        self.config = Configuration()
        self.reads = []
        self.new_reads_index = 0

    def __str__(self):
        return 'Chip (id: {}, key: {})'.format(self.chip_id, str(self.chip_key))

    def __repr__(self):
        return 'Chip(chip_key={})'.format(str(self.chip_key))

    @property
    def chip_id(self):
        return self.chip_key.chip_id

    @chip_id.setter
    def chip_id(self, val):
        self.chip_key.chip_id = val

    def get_configuration_packets(self, packet_type, registers=None):
        '''
        Return a list of Packet objects to read or write (depending on
        ``packet_type``) the specified configuration registers (or all
        registers by default).

        '''
        if registers is None:
            registers = range(Configuration.num_registers)
        conf = self.config
        packets = []
        packet_register_data = conf.all_data()
        for i, data in enumerate(packet_register_data):
            if i not in registers:
                continue
            packet = Packet()
            packet.packet_type = packet_type
            packet.chipid = self.chip_id
            packet.chip_key = self.chip_key
            packet.register_address = i
            if packet_type == Packet.CONFIG_WRITE_PACKET:
                packet.register_data = data
            else:
                packet.register_data = 0
            packet.assign_parity()
            packets.append(packet)
        return packets

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
                    if packet.packet_type == Packet.CONFIG_READ_PACKET:
                        updates[packet.register_address] = packet.register_data
        else:
            for packet in self.reads[index]:
                if packet.packet_type == Packet.CONFIG_READ_PACKET:
                    updates[packet.register_address] = packet.register_data
        self.config.from_dict_registers(updates)

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
