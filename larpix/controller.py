from collections import OrderedDict
import warnings
import time
import json
import math
import networkx as nx
from copy import copy

from . import configs
from .key import Key
from .chip import Chip
from .configuration import Configuration_v1, Configuration_v2
from .packet import Packet_v1, Packet_v2, PacketCollection

class Controller(object):
    '''
    Controls a collection of LArPix Chip objects.

    Reading data:

    The specific interface for reading data is selected by specifying
    the ``io`` attribute. These objects all have
    similar behavior for reading in new data. On initialization, the
    object will discard any LArPix packets sent from ASICs. To begin
    saving incoming packets, call ``start_listening()``.
    Data will then build up in some form of internal register or queue.
    The queue can be emptied with a call to ``read()``,
    which empties the queue and returns a list of Packet objects that
    were in the queue. The ``io`` object will still be listening for
    new packets during and after this process. If the queue/register
    fills up, data may be discarded/lost. To stop saving incoming
    packets and retrieve any packets still in the queue, call
    ``stop_listening()``. While the Controller is listening,
    packets can be sent using the appropriate methods without
    interrupting the incoming data stream.

    Properties and attributes:

    - ``chips``: the ``Chip`` objects that the controller controls
    - ``reads``: list of all the PacketCollections that have been sent
      back to this controller. PacketCollections are created by
      ``run``, ``write_configuration``, ``read_configuration``,
      ``multi_write_configuration``, ``multi_read_configuration``, and
      ``store_packets``.
    - ``network``: a collection of networkx directed graph objects representing
      the miso_us, miso_ds, and mosi connections between chips (not applicable
      for v1 asics)

    '''

    def __init__(self):
        self.chips = OrderedDict()
        self.network = OrderedDict()
        self.reads = []
        self.nreads = 0
        self.io = None
        self.logger = None

    def __getitem__(self, key):
        '''
        Retrieve the Chip object that this Controller associated with the key.
        A key can either be a valid keystring, ``larpix.Key`` object or a
        ``tuple``/``list``. If it is a ``tuple``/``list``, the chip with a key
        of ``Key(*key)`` will be retrieved.

        Raises a ``ValueError`` if no chip is found.

        E.g.::

            controller[1,1,2] == controller['1-1-2'] # access chip with key 1-1-2
            controller[1,1,2] == controller[Key('1-1-2')]

        '''
        return self._get_chip(key)

    def _get_chip(self, key):
        try:
            if isinstance(key, (str,Key)):
                return self.chips[key]
            elif isinstance(key, (tuple,list)):
                return self.chips[Key(*key)]
            raise KeyError
        except KeyError:
            raise ValueError('Could not find chip using key <{}> '.format(key))

    def add_chip(self, chip_key, version=2, config=None, root=False):
        '''
        Add a specified chip to the Controller chips.

        :param chip_key: chip key to specify unique chip

        :param version: asic version of chip

        :param config: configuration to assign chip when creating (otherwise uses default)

        :param root: specifies if this is a root node as used by the hydra io network

        :returns: ``Chip`` that was added

        '''
        if chip_key in self.chips:
            raise KeyError('chip with key {} already exists!'.format(chip_key))
        key = Key(chip_key)
        io_group, io_channel = key.io_group, key.io_channel
        self.chips[key] = Chip(chip_key=chip_key, version=version)
        self.add_network_node(io_group, io_channel, ('mosi','miso_us','miso_ds'), key.chip_id, root)

        if not config is None:
            self[chip_key].config = config
        return self.chips[chip_key]

    def add_network_link(self, io_group, io_channel, network_name, chip_ids, uart):
        '''
        Adds a link within the specified network (``mosi``, ``miso_ds``, or ``miso_us``)
        on the specified uart. Directionality is important: first key represents
        the tail (where packets are coming from) and the second is the head
        (where packets are going). The uart channel refers to the tail's uart
        channel (for ``'miso_*'``) and to the head's uart channel for (``'mosi'``).
        Links can be formed with non-key objects to allow for network
        communications with objects that are not larpix chips (e.g. an external
        fpga).

        For example to specify a miso downstream link between chips ``'1-1-3'``
        and ``'1-1-2'`` on chip ``'1-1-3'``'s uart 0, the arguments should be::

            controller.add_network_link('miso_ds', 1, 1, (3,2), 0)

        This represents a link where chip ``'1-1-3'`` will transfer packets out of
        its uart 0 to a destination of chip ``'1-1-2'`` (unspecified uart).

        No network validation is performed, so use with caution!

        :param network_name: ``str`` from ``('miso_us','miso_ds','mosi')``

        :param io_group: io group to add network link in

        :param io_channel: io channel to add network link in

        :param chip_ids: ``tuple`` of two chip ids to link (order is important -- first is 'tail' second is 'head', data flows from the 'tail' to the 'head' in all networks)

        :param uart: ``int`` referring to which uart channel this link occurs over, for ``'miso_*'`` networks the uart channel refers to the uart on the sender (i.e. the 'tail' of the edge in the directed graph), but for ``'mosi'`` networks the uart channel refers to the uart on the receiver (i.e. the 'head' of the edge in the directed graph)

        '''
        if not chip_ids[0] in self.network[io_group][io_channel][network_name]:
            self.add_network_node(io_group, io_channel, network_name, chip_ids[0])
        if not chip_ids[1] in self.network[io_group][io_channel][network_name]:
            self.add_network_node(io_group, io_channel, network_name, chip_ids[1])
        self.network[io_group][io_channel][network_name].add_edge(*chip_ids, uart=uart)

    def add_network_node(self, io_group, io_channel, network_names, chip_id, root=False):
        '''
        Adds a node to the specified network (``mosi``, ``miso_ds``, or ``miso_us``)
        with no links. Generally, this is not needed as network nodes are added
        automatically with the ``controller.add_chip()`` method. 'Special'
        (i.e. non-key) nodes can be specified to insert nodes that do not
        represent larpix chips (e.g. an external fpga). A node can be declared as
        a root node, which is used as a flag to select the starting node during
        initialization.

        :param network_names: list of networks or name of single network to create a node in

        :param io_group: io group to create node within

        :param io_channel: io channel to create node within

        :param chip_id: chip id to associate with node (note that all chip ids must be unique on a network)

        :param root: specifies if this node should be a root node (default=False)

        '''
        if not io_group in self.network.keys():
            self.network[io_group] = OrderedDict()
        if not io_channel in self.network[io_group].keys():
            self.network[io_group][io_channel] = {}
        if isinstance(network_names, str):
            if not network_names in self.network[io_group][io_channel].keys():
                self.network[io_group][io_channel][network_names] = nx.DiGraph()
        else:
            for name in network_names:
                if not name in self.network[io_group][io_channel].keys():
                    self.network[io_group][io_channel][name] = nx.DiGraph()

        if isinstance(network_names, str):
            self.network[io_group][io_channel][network_names].add_node(chip_id, root=root)
        else:
            for name in network_names:
                self.network[io_group][io_channel][name].add_node(chip_id, root=root)

    def remove_chip(self, chip_key):
        '''
        Remove a specified chip from the Controller chips.

        :param chip_key: chip key to specify unique chip

        '''
        chip_key = Key(chip_key)
        io_channel, io_group = chip_key.io_channel, chip_key.io_group
        del self.chips[chip_key]

        self.network[io_group][io_channel]['mosi'].remove_node(chip_key.chip_id)
        self.network[io_group][io_channel]['miso_us'].remove_node(chip_key.chip_id)
        self.network[io_group][io_channel]['miso_ds'].remove_node(chip_key.chip_id)

    def load(self, filename):
        '''
        Loads the specified file that describes the chip ids and IO network

        :param filename: File path to configuration file

        '''
        system_info = configs.load(filename, 'controller')
        if system_info['asic_version'] == 1:
            print('loading v1 controller...')
            return self.load_controller(filename)
        if system_info['asic_version'] == 2:
            print('loading v2 network...')
            return self.load_network(filename)

    def load_network(self, filename):
        '''
        Loads the specified file using hydra io network configuration format

        After loading the network, running
        ``controller.init_network(<io group>, <io channel>)`` will configure the
        chips with specified chip ids in the order declared in file

        :param filename: File path to configuration file

        '''
        system_info = configs.load(filename)
        inherited_data = ('miso_us_uart_map', 'miso_ds_uart_map', 'mosi_uart_map')
        orig_chips = copy(self.chips)
        orig_network = copy(self.network)
        try:
            def inherit_values(child_dict, parent_dict, value_keys):
                return dict([(key, child_dict[key])
                        if key in child_dict else (key, parent_dict[key])
                        for key in value_keys])

            self.chips = OrderedDict()
            for io_group, group_spec in system_info['network'].items():
                if io_group in inherited_data:
                    continue
                io_group_inherited_data = inherit_values(group_spec, system_info['network'], inherited_data)

                for io_channel, channel_spec in system_info['network'][io_group].items():
                    if io_channel in inherited_data:
                        continue
                    io_channel_inherited_data = inherit_values(channel_spec, io_group_inherited_data, inherited_data)

                    for chip_spec in channel_spec['chips']:
                        chip_inherited_data = inherit_values(chip_spec, io_channel_inherited_data, inherited_data)

                        io_group = int(io_group)
                        io_channel = int(io_channel)
                        chip_id = chip_spec['chip_id']
                        chip_key = Key(io_group, io_channel, chip_id)
                        root = False
                        if 'root' in chip_spec and chip_spec['root']:
                            root = True

                        self.add_chip(chip_key, version=2, root=root)

                        subnetwork = self.network[io_group][io_channel]

                        if 'miso_us' in chip_spec:
                            for idx, uart in enumerate(chip_inherited_data['miso_us_uart_map']):
                                link = (chip_id, chip_spec['miso_us'][idx])
                                if link[1] is None:
                                    continue
                                self.add_network_link(io_group, io_channel, 'miso_us', link, uart)

                        if 'miso_ds' in chip_spec:
                            for idx, uart in enumerate(chip_inherited_data['miso_ds_uart_map']):
                                link = (chip_id, chip_spec['miso_ds'][idx])
                                if link[1] is None:
                                    continue
                                self.add_network_link(io_group, io_channel, 'miso_ds', link, uart)
                        elif subnetwork['miso_us'].in_edges(chip_id):
                            for link in subnetwork['miso_us'].in_edges(chip_id):
                                other_chip_id = link[0]
                                other_spec = [spec for spec in channel_spec['chips'] if spec['chip_id'] == other_chip_id][0]
                                uart = chip_inherited_data['miso_ds_uart_map'][other_spec['miso_us'].index(chip_id)]
                                link = (chip_id, other_chip_id)
                                self.add_network_link(io_group, io_channel, 'miso_ds', link, uart)

                        if 'mosi' in chip_spec:
                            for idx, uart in enumerate(chip_inherited_data['mosi_uart_map']):
                                link = (chip_id, chip_spec['miso_us'][idx])
                                if link[1] is None:
                                    continue
                                self.add_network_link(io_group, io_channel, 'mosi', link, uart)
                        else:
                            for link in subnetwork['miso_us'].in_edges():
                                self.add_network_link(io_group, io_channel, 'mosi', link[::-1], subnetwork['miso_us'].edges[link]['uart'])
                            for link in subnetwork['miso_ds'].in_edges():
                                self.add_network_link(io_group, io_channel, 'mosi', link[::-1], subnetwork['miso_ds'].edges[link]['uart'])
        except Exception as err:
            self.chips = orig_chips
            self.network = orig_network
            raise err

        return system_info['name']

    def load_controller(self, filename):
        '''
        Loads the specified file using the basic key, chip format

        The chip key is the Controller access key that gets communicated to/from
        the io object when sending and receiving packets.

        :param filename: File path to configuration file

        '''
        system_info = configs.load(filename)
        chips = OrderedDict()
        for chip_keystring in system_info['chip_list']:
            chip_key = Key(str(chip_keystring))
            chips[chip_key] = Chip(chip_key=chip_key, version=1)
        self.chips = chips
        return system_info['name']

    def init_network(self, io_group=1, io_channel=1, chip_id=None):
        '''
        Configure a Hydra io node specified by chip_id, if none are specified,
        load complete network
        To configure a Hydra io network, the following steps are followed:

         - Enable miso_us of parent chip
         - Write chip_id to chip on io group + io channel (assuming chip id 1)
         - Write enable_miso_downstream to chip chip_id
         - Write enable_mosi to chip chip_id

        '''
        subnetwork = self.network[io_group][io_channel]
        if chip_id is None:
            chip_ids = [chip_id for chip_id in subnetwork['miso_us'].nodes() if subnetwork['miso_us'].nodes[chip_id]['root']]

            while chip_ids:
                for chip_id in chip_ids:
                    if isinstance(chip_id, int):
                        self.init_network(io_group, io_channel, chip_id=chip_id)
                chip_ids = [link[1] for link in subnetwork['miso_us'].out_edges(chip_ids)]
            return

        packets = []
        chip_key = Key(io_group, io_channel, chip_id)

        # Enable miso_upstream on parent chips
        for us_link in subnetwork['miso_us'].in_edges(chip_id):
            if not isinstance(us_link[0], int):
                continue
            parent_chip_id = us_link[0]
            parent_chip_key = Key(io_group, io_channel, parent_chip_id)
            parent_uart = subnetwork['miso_us'].edges[us_link]['uart']
            self[parent_chip_key].config.enable_miso_upstream[parent_uart] = 1
            packets += self[parent_chip_key].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_miso_upstream'])

        # Write chip_id to specified chip (assuming it has chip id 1)
        self[chip_key].config.chip_id = chip_key.chip_id
        packets += self[chip_key].get_configuration_write_packets(registers=Configuration_v2.register_map['chip_id'])
        packets[-1].chip_id = 1

        # Enable miso_downstream, mosi on chip
        self[chip_key].config.enable_miso_downstream = [0]*4
        for ds_link in subnetwork['miso_ds'].out_edges(chip_id):
            ds_uart = subnetwork['miso_ds'].edges[ds_link]['uart']
            self[chip_key].config.enable_miso_downstream[ds_uart] = 1
        packets += self[chip_key].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_miso_downstream'])

        self[chip_key].config.enable_mosi = [0]*4
        for mosi_link in subnetwork['mosi'].in_edges(chip_id):
            mosi_uart = subnetwork['mosi'].edges[mosi_link]['uart']
            self[chip_key].config.enable_mosi[mosi_uart] = 1
        packets += self[chip_key].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_mosi'])

        self.send(packets)

    def reset_network(self, io_group=1, io_channel=1, chip_id=None):
        '''
        Resets the hydra IO network
        To reset a Hydra io network node, the following steps are followed:

         - Write enable_mosi [1,1,1,1] to chip
         - Write enable_miso_downstream [0,0,0,0] to chip
         - Write chip_id 1 to chip
         - Disable miso_us channel of parent chip

        If no chip_id is specified, network is reset in reverse order (starting
        from chips with no outgoing miso_us connections, working up the miso_us
        tree)

        '''
        subnetwork = self.network[io_group][io_channel]
        if chip_id is None:
            chip_ids = [chip_id for chip_id in subnetwork['miso_us'].nodes() if not subnetwork['miso_us'].out_edges(chip_id)]

            while chip_ids:
                for chip_id in chip_ids:
                    if isinstance(chip_id, int):
                        self.reset_network(io_group, io_channel, chip_id=chip_id)
                chip_ids = [link[0] for link in subnetwork['miso_us'].in_edges(chip_ids)]
            return

        packets = []
        chip_key = Key(io_group, io_channel, chip_id)

        # Enable mosi
        self[chip_key].config.enable_mosi = [1]*4
        packets += self[chip_key].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_mosi'])

        # Disable miso_downstream
        self[chip_key].config.enable_miso_downstream = [0]*4
        packets += self[chip_key].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_miso_downstream'])

        # Write default chip_id to specified chip
        self[chip_key].config.chip_id = 1
        packets += self[chip_key].get_configuration_write_packets(registers=Configuration_v2.register_map['chip_id'])

        # Disable miso_upstream on parent chips
        for us_link in subnetwork['miso_us'].in_edges(chip_id):
            if not isinstance(us_link[0], int):
                continue
            parent_chip_id = us_link[0]
            parent_chip_key = Key(io_group, io_channel, parent_chip_id)
            parent_uart = subnetwork['miso_us'].edges[us_link]['uart']
            self[parent_chip_key].config.enable_miso_upstream[parent_uart] = 0
            packets += self[parent_chip_key].get_configuration_write_packets(registers=Configuration_v2.register_map['enable_miso_upstream'])

        self.send(packets)


    def send(self, packets):
        '''
        Send the specified packets to the LArPix ASICs.

        '''
        timestamp = time.time()
        if self.io:
            self.io.send(packets)
        else:
            warnings.warn('no IO object exists, no packets sent', RuntimeWarning)
        if self.logger:
            self.logger.record(packets, direction=self.logger.WRITE)

    def start_listening(self):
        '''
        Listen for packets to arrive.

        '''
        if self.io:
            self.io.start_listening()
        else:
            warnings.warn('no IO object exists, you have done nothing', RuntimeWarning)

    def stop_listening(self):
        '''
        Stop listening for new packets to arrive.

        '''
        if self.io:
            return self.io.stop_listening()
        else:
            warnings.warn('no IO object exists, you have done nothing', RuntimeWarning)

    def read(self):
        '''
        Read any packets that have arrived and return (packets,
        bytestream) where bytestream is the bytes that were received.

        The returned list will contain packets that arrived since the
        last call to ``read`` or ``start_listening``, whichever was most
        recent.

        '''
        timestamp = time.time()
        packets = []
        bytestream = b''
        if self.io:
            packets, bytestream = self.io.empty_queue()
        else:
            warnings.warn('no IO object exists, no packets will be received', RuntimeWarning)
        if self.logger:
            self.logger.record(packets, direction=self.logger.READ)
        return packets, bytestream

    def write_configuration(self, chip_key, registers=None, write_read=0,
            message=None):
        '''
        Send the configurations stored in chip.config to the LArPix
        ASIC.

        By default, sends all registers. If registers is an int, then
        only that register is sent. If registers is an iterable, then
        all of the registers in the iterable are sent.

        If write_read == 0 (default), the configurations will be sent
        and the current listening state will not be affected. If the
        controller is currently listening, then the listening state
        will not change and the value of write_read will be ignored. If
        write_read > 0 and the controller is not currently listening,
        then the controller will listen for ``write_read`` seconds
        beginning immediately before the packets are sent out, read the
        io queue, and save the packets into the ``reads`` data member.
        Note that the controller will only read the queue once, so if a
        lot of data is expected, you should handle the reads manually
        and set write_read to 0 (default).

        '''
        chip = self[chip_key]
        if registers is None:
            registers = list(range(chip.config.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        if message is None:
            message = 'configuration write'
        else:
            message = 'configuration write: ' + message
        packets = chip.get_configuration_write_packets(registers)
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        mess_with_listening = write_read != 0 and not already_listening
        if mess_with_listening:
            self.start_listening()
            stop_time = time.time() + write_read
        self.send(packets)
        if mess_with_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def read_configuration(self, chip_key, registers=None, timeout=1,
            message=None):
        '''
        Send "configuration read" requests to the LArPix ASIC.

        By default, request all registers. If registers is an int, then
        only that register is reqeusted. If registers is an iterable,
        then all of the registers in the iterable are requested.

        If the controller is currently listening, then the requests
        will be sent and no change to the listening state will occur.
        (The value of ``timeout`` will be ignored.) If the controller
        is not currently listening, then the controller will listen
        for ``timeout`` seconds beginning immediately before the first
        packet is sent out, and will save any received packets in the
        ``reads`` data member.

        '''
        chip = self[chip_key]
        if registers is None:
            registers = list(range(chip.config.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        if message is None:
            message = 'configuration read'
        else:
            message = 'configuration read: ' + message
        packets = chip.get_configuration_read_packets(registers)
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        if not already_listening:
            self.start_listening()
            stop_time = time.time() + timeout
        self.send(packets)
        if not already_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def multi_write_configuration(self, chip_reg_pairs, write_read=0,
            message=None):
        '''
        Send multiple write configuration commands at once.

        ``chip_reg_pairs`` should be a list/iterable whose elements are
        an valid arguments to ``Controller.write_configuration``,
        excluding the ``write_read`` argument. Just like in the single
        ``Controller.write_configuration``, setting ``write_read > 0`` will
        have the controller read data during and after it writes, for
        however many seconds are specified.

        Examples:

        These first 2 are equivalent and write the full configurations

        >>> controller.multi_write_configuration([chip_key1, chip_key2, ...])
        >>> controller.multi_write_configuration([(chip_key1, None), chip_key2, ...])

        These 2 write the specified registers for the specified chips
        in the specified order

        >>> controller.multi_write_configuration([(chip_key1, 1), (chip_key2, 2), ...])
        >>> controller.multi_write_configuration([(chip_key1, range(10)), chip_key2, ...])

        '''
        if message is None:
            message = 'multi configuration write'
        else:
            message = 'multi configuration write: ' + message
        packets = []
        for chip_reg_pair in chip_reg_pairs:
            if not isinstance(chip_reg_pair, tuple):
                chip_reg_pair = (chip_reg_pair, None)
            chip_key, registers = chip_reg_pair
            chip = self[chip_key]
            if registers is None:
                registers = list(range(chip.config.num_registers))
            elif isinstance(registers, int):
                registers = [registers]
            else:
                pass
            one_chip_packets = chip.get_configuration_write_packets(registers)
            packets.extend(one_chip_packets)
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        mess_with_listening = write_read != 0 and not already_listening
        if mess_with_listening:
            self.start_listening()
            stop_time = time.time() + write_read
        self.send(packets)
        if mess_with_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            #time.sleep(stop_time - time.time())
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def multi_read_configuration(self, chip_reg_pairs, timeout=1,
            message=None):
        '''
        Send multiple read configuration commands at once.

        ``chip_reg_pairs`` should be a list/iterable whose elements are
        chip keys (to read entire configuration) or (chip_key, registers)
        tuples to read only the specified register(s). Registers could
        be ``None`` (i.e. all), an ``int`` for that register only, or an
        iterable of ints.

        Examples:

        These first 2 are equivalent and read the full configurations

        >>> controller.multi_read_configuration([chip_key1, chip_key2, ...])
        >>> controller.multi_read_configuration([(chip_key1, None), chip_key2, ...])

        These 2 read the specified registers for the specified chips
        in the specified order

        >>> controller.multi_read_configuration([(chip_key1, 1), (chip_key2, 2), ...])
        >>> controller.multi_read_configuration([(chip_key1, range(10)), chip_key2, ...])

        '''
        if message is None:
            message = 'multi configuration read'
        else:
            message = 'multi configuration read: ' + message
        packets = []
        for chip_reg_pair in chip_reg_pairs:
            if not isinstance(chip_reg_pair, tuple):
                chip_reg_pair = (chip_reg_pair, None)
            chip_key, registers = chip_reg_pair
            chip = self[chip_key]
            if registers is None:
                registers = list(range(chip.config.num_registers))
            elif isinstance(registers, int):
                registers = [registers]
            else:
                pass
            one_chip_packets = chip.get_configuration_read_packets(registers)
            packets += one_chip_packets
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        if not already_listening:
            self.start_listening()
            stop_time = time.time() + timeout
        self.send(packets)
        if not already_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            #time.sleep(stop_time - time.time())
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def run(self, timelimit, message):
        '''
        Read data from the LArPix ASICs for the given ``timelimit`` and
        associate the received Packets with the given ``message``.

        '''
        sleeptime = 0.1
        self.start_listening()
        start_time = time.time()
        packets = []
        bytestreams = []
        while time.time() - start_time < timelimit:
            time.sleep(sleeptime)
            read_packets, read_bytestream = self.read()
            packets.extend(read_packets)
            bytestreams.append(read_bytestream)
        self.stop_listening()
        data = b''.join(bytestreams)
        self.store_packets(packets, data, message)

    def verify_registers(self, chip_key_register_pairs, timeout=0.1):
        '''
        Read chip configuration from specified chip and registers and return ``True`` if the
        read chip configuration matches the current configuration stored in chip instance.
        ``chip_key`` is a single chip key.

        :param chip_key_register_pair: a ``list`` of key register pairs as documented in ``controller.multi_read_configuration``

        :param timeout: set how long to wait for response in seconds (optional)

        :returns: 2-``tuple`` of a ``bool`` representing if all registers match and a ``dict`` representing all differences. Differences are specified as ``{<chip_key>: {<register>: (<expected>, <read>)}}``

        '''
        return_value = True
        different_fields = {}
        registers = dict(chip_key_register_pairs)
        for chip_key, chip_registers in registers.items():
            if not isinstance(chip_registers, (list,tuple,range)):
                registers[chip_key] = [chip_registers]
        chip_keys = registers.keys()
        self.multi_read_configuration(chip_key_register_pairs, timeout=timeout)
        configuration_data = dict([
            (chip_key, dict([(register,(None, None)) for register in chip_registers])) for chip_key, chip_registers in registers.items()])
        for packet in self.reads[-1]:
            packet_key = packet.chip_key
            if (packet.packet_type == packet.CONFIG_READ_PACKET):
                register_address = packet.register_address
                if packet_key in configuration_data and register_address in configuration_data[packet_key]:
                    configuration_data[packet_key][register_address] = (None, packet.register_data)

        for chip_key in chip_keys:
            expected_data = dict([(register_address, int(bits.to01(),2)) for register_address, bits in enumerate(self[chip_key].config.all_data())])
            for register in registers[chip_key]:
                configuration_data[chip_key][register] = (expected_data[register], configuration_data[chip_key][register][1])
                if not configuration_data[chip_key][register][0] == configuration_data[chip_key][register][1]:
                    return_value = False
                else:
                    del configuration_data[chip_key][register]
            if not len(configuration_data[chip_key]):
                del configuration_data[chip_key]
        return (return_value, configuration_data)

    def verify_configuration(self, chip_keys=None, timeout=0.1):
        '''
        Read chip configuration from specified chip(s) and return ``True`` if the
        read chip configuration matches the current configuration stored in chip instance.
        ``chip_keys`` can be a single chip key, a list of chip keys, or ``None``. If
        ``chip_keys`` is ``None`` all chips will be verified.

        Also returns a dict containing the values of registers that are different
        (read register, stored register)

        :param chip_keys: ``list`` of chip_keys to verify

        :param timeout: how long to wait for response in seconds

        :returns: 2-``tuple`` with same format as ``controller.verify_registers``

        '''
        if chip_keys is None:
            chip_keys = self.chips.keys()
        if isinstance(chip_keys,(str,Key)):
            chip_keys = [chip_keys]
        chip_key_register_pairs = [(chip_key, range(self[chip_key].config.num_registers)) for chip_key in chip_keys]
        return self.verify_registers(chip_key_register_pairs, timeout=timeout)

    def verify_network(self, chip_keys=None, timeout=0.1):
        '''
        Read chip network configuration from specified chip(s) and return ``True``
        if the read chip configurations matches
        Only valid for v2 chips.

        :param chip_keys: ``list`` of chip_keys to verify or singe chip_key to verify

        :param timeout: how long to wait for response in seconds

        :returns: 2-``tuple`` with same format as ``controller.verify_registers``

        '''
        if not chip_keys:
            chip_keys = self.chips.keys()
        if isinstance(chip_keys,(str,Key)):
            chip_keys = [chip_keys]
        network_registers = list(Configuration_v2.register_map['chip_id']) + \
            list(Configuration_v2.register_map['enable_mosi']) + \
            list(Configuration_v2.register_map['enable_miso_upstream']) + \
            list(Configuration_v2.register_map['enable_miso_downstream'])
        chip_key_register_pairs = [(chip_key, network_registers) for chip_key in chip_keys]
        return self.verify_registers(chip_key_register_pairs)

    def enable_analog_monitor(self, chip_key, channel):
        '''
        Enable the analog monitor on a single channel on the specified chip.
        Note: If monitoring a different chip, call disable_analog_monitor first to ensure
        that the monitor to that chip is disconnected.
        '''
        chip = self[chip_key]
        if chip.asic_version == 1:
            chip.config.disable_analog_monitor()
            chip.config.enable_analog_monitor(channel)
            self.write_configuration(chip_key, chip.config.csa_monitor_select_addresses)
        elif chip.asic_version == 2:
            chip.config.csa_monitor_select = [0]*chip.config.num_channels
            chip.config.csa_monitor_select[channel] = 1
            self.write_configuration(chip_key, chip.config.register_map['csa_monitor_select'])
        else:
            raise RuntimeError('chip has invalid asic version')
        return

    def disable_analog_monitor(self, chip_key=None, channel=None):
        '''
        Disable the analog monitor for a specified chip and channel, if none are specified
        disable the analog monitor for all chips in self.chips and all channels
        '''
        if chip_key is None:
            for chip in self.chips:
                self.disable_analog_monitor(chip_key=chip_key, channel=channel)
        elif channel is None:
            for channel in range(self[chip_key].config.num_channels):
                self.disable_analog_monitor(chip_key=chip_key, channel=channel)
        else:
            chip = self[chip_key]
            if chip.asic_version == 1:
                chip.config.disable_analog_monitor()
                self.write_configuration(chip_key, chip.config.csa_monitor_select_addresses)
            elif chip.asic_version == 2:
                chip.config.csa_monitor_select[channel] = 0
                self.write_configuration(chip_key, chip.config.register_map['csa_monitor_select'])
            else:
                raise RuntimeError('chip has invalid asic version')
        return

    def enable_testpulse(self, chip_key, channel_list, start_dac=255):
        '''
        Prepare chip for pulsing - enable testpulser and set a starting dac value for
        specified chip/channel
        '''
        chip = self[chip_key]
        if chip.asic_version == 1:
            chip.config.disable_testpulse()
            chip.config.enable_testpulse(channel_list)
            chip.config.csa_testpulse_dac_amplitude = start_dac
            self.write_configuration(chip_key, chip.config.csa_testpulse_enable_addresses +
                                     [chip.config.csa_testpulse_dac_amplitude_address])
        elif chip.asic_version == 2:
            chip.config.csa_testpulse_enable = [1]*chip.config.num_channels
            for channel in channel_list:
                chip.config.csa_testpulse_enable[channel] = 0
            chip.config.csa_testpulse_dac = start_dac
            self.write_configuration(chip_key, list(chip.config.register_map['csa_testpulse_dac']) + list(chip.config.register_map['csa_testpulse_enable']))
        else:
            raise RuntimeError('chip has invalid asic version')
        return

    def issue_testpulse(self, chip_key, pulse_dac, min_dac=0, read_time=0.1):
        '''
        Reduce the testpulser dac by ``pulse_dac`` and write_read to chip for
        ``read_time`` seconds

        '''
        chip = self[chip_key]
        if chip.asic_version == 1:
            chip.config.csa_testpulse_dac_amplitude -= pulse_dac
            if chip.config.csa_testpulse_dac_amplitude < min_dac:
                raise ValueError('Minimum DAC exceeded')
            self.write_configuration(chip_key, [chip.config.csa_testpulse_dac_amplitude_address],
                                     write_read=read_time)
        elif chip.asic_version == 2:
            if chip.config.csa_testpulse_dac - pulse_dac < min_dac:
                raise ValueError('Minimum DAC exceeded')
            try:
                chip.config.csa_testpulse_dac -= pulse_dac
            except ValueError:
                raise ValueError('Minimum DAC exceeded')
            self.write_configuration(chip_key, chip.config.register_map['csa_testpulse_dac'], write_read=read_time)
        return self.reads[-1]

    def disable_testpulse(self, chip_key=None, channel_list=None):
        '''
        Disable testpulser for specified chip/channels. If none specified, disable for
        all chips/channels
        '''
        if chip_key is None:
            for chip_key in self.chips.keys():
                self.disable_testpulse(chip_key=chip_key, channel_list=channel_list)
        if channel_list is None:
            channel_list = range(self[chip_key].config.num_channels)
            self.disable_testpulse(chip_key=chip_key, channel_list=channel_list)
        else:
            chip = self[chip_key]
            if chip.asic_version == 1:
                chip.config.disable_testpulse(channel_list)
                self.write_configuration(chip_key, chip.conf.csa_testpulse_enable_addresses)
            elif chip.asic_version == 2:
                for channel in channel_list:
                    chip.config.csa_testpulse_enable[channel] = 1
                self.write_configuration(chip_key, chip.conf.register_map['csa_testpulse_enable'])
            else:
                raise RuntimeError('chip has invalid asic version')
        return

    def disable(self, chip_key=None, channel_list=None):
        '''
        Update channel mask to disable specified chips/channels. If none specified,
        disable all chips/channels
        '''
        if chip_key is None:
            for chip_key in self.chips.keys():
                self.disable(chip_key=chip_key, channel_list=channel_list)
        else:
            chip = self[chip_key]
            if channel_list is None:
                channel_list = range(chip.config.num_channels)
            if chip.asic_version == 1:
                chip.config.disable_channels(channel_list)
                self.write_configuration(chip_key, Configuration_v1.channel_mask_addresses)
            elif chip.asic_version == 2:
                for channel in channel_list:
                    chip.config.channel_mask[channel] = 1
                    self.write_configuration(chip_key, chip.config.register_map['channel_mask'])
            else:
                raise RuntimeError('chip has invalid asic version')

    def enable(self, chip_key=None, channel_list=None):
        '''
        Update channel mask to enable specified chips/channels. If none specified,
        enable all chips/channels
        '''
        if chip_key is None:
            for chip_key in self.chips.keys():
                self.enable(chip_key=chip_key, channel_list=channel_list)
        else:
            chip = self[chip_key]
            if channel_list is None:
                channel_list = range(chip.config.num_channels)
            if chip.asic_version == 1:
                chip.config.enable_channels(channel_list)
                self.write_configuration(chip_key, Configuration_v1.channel_mask_addresses)
            elif chip.asic_version == 2:
                for channel in channel_list:
                    chip.config.channel_mask[channel] = 0
                self.write_configuration(chip_key, chip.config.register_map['channel_mask'])
            else:
                raise RuntimeError('chip has invalid asic version')

    def store_packets(self, packets, data, message):
        '''
        Store the packets in ``self`` and in ``self.chips``

        '''
        new_packets = PacketCollection(packets, data, message)
        new_packets.read_id = self.nreads
        self.nreads += 1
        self.reads.append(new_packets)
        #self.sort_packets(new_packets)

    def sort_packets(self, collection):
        '''
        Sort the packets in ``collection`` into each chip in ``self.chips``

        '''
        by_chip_key = collection.by_chip_key()
        for chip_key in by_chip_key.keys():
            if chip_key in self.chips.keys():
                chip = self[chip_key]
                chip.reads.append(by_chip_key[chip_key])
            elif not self._test_mode:
                print('Warning chip key {} not in chips.'.format(chip_key))

    def save_output(self, filename, message):
        '''Save the data read by each chip to the specified file.'''
        data = {}
        data['reads'] = [collection.to_dict() for collection in self.reads]
        data['chips'] = [repr(chip) for chip in self.chips.values()]
        data['message'] = message
        with open(filename, 'w') as outfile:
            json.dump(data, outfile, indent=4,
                    separators=(',',':'), sort_keys=True)
