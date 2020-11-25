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
from .configuration import Configuration_v1, Configuration_v2, Configuration_Lightpix_v1
from .packet import Packet_v1, Packet_v2, PacketCollection
from . import bitarrayhelper as bah

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

    With the the LArPix v2 asic, a network io structure is used. To keep track of
    this network and to insure the proper bring-up procedure is followed. The
    controller has a ``network`` attribute. This is an ordered dict with multiple
    layers corresponding to the chip key layers. It assumes that each hydra network
    is distinct on a given io channel. On a given io channel, the hydra network is
    represented as three directed graphs ``miso_us``, ``miso_ds``, and ``mosi``.::

        controller.network[1] # Represents all networks on io group 1
        controller.network[1][1] # Represents the network on io group 1, io channel 1
        controller.network[1][1]['mosi'] # directed graph representing mosi links

    Nodes within the network are added automatically whenever you add a chip to the
    controller::

        list(controller.network[1][1]['mosi'].nodes()) # chip ids of known mosi nodes
        list(controller.network[1][1]['miso_us'].nodes()) # chip ids of known miso_us nodes
        list(controller.network[1][1]['miso_ds'].nodes()) # chip ids of known miso_ds nodes
        controller.network[1][1]['miso_us'].nodes[5] # attributes associated with node 5
        controller.add_chip('1-1-6', version=2, root=True)
        list(controller.network[1][1]['miso_us'].nodes()) # [5, 6]


    The 'root' node is used to indicate which chips should be brought up first when
    initializing the network.

    Accessing connections between nodes is done via edges::

        list(controller.network[1][1]['miso_us'].edges()) # []
        controller.add_network_link(1,1,'miso_us',(6,5),0) # link chips 6 -> 5 in the miso_us graph via chip 6's uart channel 0
        list(controller.network[1][1]['miso_us'].edges()) # [(6,5)] direction indicates the data flow direction
        controller.network[1][1]['miso_us'].edges[(6,5)] # attributes associated with link ('uart': 0)

    In order to set up a 'working' network, you'll need to add the proper links in
    the miso_ds and mosi graphs as well.::

        controller.add_network_link(1,1,'miso_ds',(5,6),2)
        controller.add_network_link(1,1,'mosi',(6,5),0)
        controller.add_network_link(1,1,'mosi',(5,6),2)

    External systems (e.g. the fpga you are using to communicate with the chips) are
    conventionally called ``'ext0', 'ext1', ...`` and shouldn't be forgotten in the
    network configuration! These nodes are used to determine the miso/mosi
    configuration for the linked chips.::

        controller.add_network_link(1,1,'mosi',('ext',6),1) # link chip 6 to 'ext' via chip 6's uart channel 0
        controller.add_network_link(1,1,'miso_ds',(6,'ext'),1) # same for miso_ds
        list(controller.network[1][1]['miso_ds'].edges())
        list(controller.network[1][1]['mosi'].edges())

    To then initialize a component on the network, run `controller.init_network(1,1,6)`.
    This will modify the correct registers of chip 1-1-6 and send the configuration
    commands to the system.::

        controller.init_network(1,1,6)
        controller.init_network(1,1,5)

    Keep in mind, the order in which you initialize the network is important (e.g.
    chip 6 needs to be initialized before chip 5 since it is upstream from chip 6).

    You may also reset a particular node with `reset_network(<io_group>,<io_channel>,<chip_id>)`
    which resets the network configuration of a particular node.::

        controller.reset_network(1,1,5)
        controller.reset_network(1,1,6)

    This is all rather tedious to do manually, so there a few shortcuts to make declaring and
    configuring the network easier. If you don't want to initialize or reset each
    node in order, you may allow the controller to figure out the proper order
    (based on the root nodes) and configure all of the chips.::

        controller.init_network(1,1) # configure the 1-1 network
        controller.reset_network(1,1) # revert the 1-1 network to it's original state

    In the event that you need to access the chip keys of a network in the order
    of their depth within the network, use::

        controller.get_network_keys(1,1) # get a list of chip keys starting with the root node and descending into the network
        controller.get_network_keys(1,1,root_first_traversal=False) # get a list of chip keys starting with the chips deepest in the network and ascending

    You may also specify a network configuration file and use this to create all
    of the necessary network links and chips. See
    <https://larpix-control.readthedocs.io/en/stable/api/configs/controller.html>
    for how to create one of these files. This is the generally recommended means of
    creating and loading a Hydra io network.::

        # as an example for bringing up a hydra network from a config file
        controller.load('<network config file>.json') # load your network and chips
        for io_group, io_channels in controller.network.items():
            for io_channel in io_channels:
                controller.init_network(io_group, io_channel) # update configurations and write to chips

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
    network_names = ('miso_us', 'miso_ds', 'mosi')

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
        self.add_network_node(io_group, io_channel, self.network_names, key.chip_id, root)

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
        self._create_network(io_group, io_channel, network_names)

        if isinstance(network_names, str):
            self.network[io_group][io_channel][network_names].add_node(chip_id, root=root)
        else:
            for name in network_names:
                self.network[io_group][io_channel][name].add_node(chip_id, root=root)

    def get_network_ids(self, io_group, io_channel, root_first_traversal=True):
        '''
        Returns a list of chip ids in order of depth within the miso_us network

        :param io_group: io group of network

        :param io_channel: io channel of network

        :param root_first_traversal: ``True`` to traverse network starting from root nodes then increasing in network depth, ``False`` to traverse network starting from nodes furthest from root nodes and then decreasing in network depth

        '''
        subnetwork = self.network[io_group][io_channel]['miso_us']
        ordered_ids = []

        chip_ids = [chip_id for chip_id in subnetwork.nodes() if subnetwork.nodes[chip_id]['root']]

        collected_chips = set(chip_ids)

        while chip_ids:
            for chip_id in chip_ids:
                ordered_ids.append(chip_id)
                collected_chips.add(chip_id)
            chip_ids = [link[1] for link in subnetwork.out_edges(chip_ids) if not link[1] in collected_chips]
        if root_first_traversal:
            return ordered_ids
        return ordered_ids[::-1]

    def get_network_keys(self, io_group, io_channel, root_first_traversal=True):
        '''
        Returns a list of chip ids in order of depth within the miso_us network

        :param io_group: io group of network

        :param io_channel: io channel of network

        :param root_first_traversal: ``True`` to traverse network starting from root nodes then increasing in network depth, ``False`` to traverse network starting from nodes furthest from root nodes and then decreasing in network depth

        '''
        chip_ids = self.get_network_ids(io_group, io_channel, root_first_traversal=root_first_traversal)
        return [Key(io_group, io_channel, chip_id) for chip_id in chip_ids if isinstance(chip_id, int)]

    def _create_network(self, io_group, io_channel, network_names):
        '''
        Creates specified network if they don't already exist

        :param network_names: list of networks or name of single network to create

        :param io_group: io group to create node within

        :param io_channel: io channel to create node within

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

    def remove_chip(self, chip_key):
        '''
        Remove a specified chip from the Controller chips.

        :param chip_key: chip key to specify unique chip

        '''
        chip_key = Key(chip_key)
        io_channel, io_group = chip_key.io_channel, chip_key.io_group
        del self.chips[chip_key]

        for network_name in self.network_names:
            self.network[io_group][io_channel][network_name].remove_node(chip_key.chip_id)

    def load(self, filename):
        '''
        Loads the specified file that describes the chip ids and IO network

        :param filename: File path to configuration file

        '''
        system_info = configs.load(filename, 'controller')
        if system_info['asic_version'] == 1:
            print('loading v1 controller...')
            return self.load_controller(filename)
        if system_info['asic_version'] in (2, 'lightpix-1'):
            print('loading v2 network...')
            return self.load_network(filename, version=system_info['asic_version'])

    def _propogate_inherited_values(self, network_spec, value_keys):
        dict_to_return = dict()
        for value_key in value_keys:
            dict_to_return[value_key] = network_spec[value_key]

        for key, group_spec in network_spec.items():
            if key in value_keys:
                continue
            dict_to_return[key] = group_spec

            for value_key in value_keys:
                if not value_key in group_spec:
                    dict_to_return[key][value_key] = dict_to_return[value_key]

            for subkey, channel_spec in network_spec[key].items():
                if subkey in value_keys:
                    continue
                for value_key in value_keys:
                    if not value_key in channel_spec:
                       dict_to_return[key][subkey][value_key] = dict_to_return[key][value_key]

                for idx, node_spec in enumerate(channel_spec['nodes']):
                    for value_key in value_keys:
                        if not value_key in node_spec:
                           dict_to_return[key][subkey]['nodes'][idx][value_key] = dict_to_return[key][subkey][value_key]

        return dict_to_return

    def _create_network_node(self, io_group, io_channel, node, version=2):
        chip_id = node['chip_id']
        if isinstance(chip_id, int):
            # create new chip object
            chip_key = Key(io_group, io_channel, chip_id)
            root = True if 'root' in node and node['root'] else False
            self.add_chip(chip_key, version=version, root=root)
        else:
            # dummy node
            root = True if 'root' in node and node['root'] else False
            self.add_network_node(io_group, io_channel, self.network_names, chip_id, root)

    def _link_miso_us_network_node(self, io_group, io_channel, node, hydra_network_nodes, mapping_spec):
        chip_id = node['chip_id']
        subnetwork = self.network[io_group][io_channel]

        if 'miso_us' in node:
            try:
                uarts = None
                if mapping_spec == 'old':
                    uarts = enumerate(node['miso_us_uart_map'])
                elif mapping_spec == 'new':
                    uarts = enumerate(node['miso_uart_map'])
                for idx, uart in uarts:
                    link = (chip_id, node['miso_us'][idx])
                    if link[1] is None: continue
                    self.add_network_link(io_group, io_channel, 'miso_us', link, uart)
            except KeyError:
                raise KeyError('error generating upstream network node {}-{}-{}'.format(io_group,io_channel,chip_id))

    def _link_miso_ds_network_node(self, io_group, io_channel, node, hydra_network_nodes, mapping_spec):
        chip_id = node['chip_id']
        subnetwork = self.network[io_group][io_channel]

        if 'miso_ds' in node:
            try:
                uarts = None
                if mapping_spec == 'old':
                    uarts = enumerate(node['miso_ds_uart_map'])
                elif mapping_spec == 'new':
                    uarts = enumerate(node['miso_uart_map'])
                for idx, uart in uarts:
                    link = (chip_id, node['miso_ds'][idx])
                    if link[1] is None: continue
                    self.add_network_link(io_group, io_channel, 'miso_ds', link, uart)
            except KeyError:
                raise KeyError('error generating downstream network node {}-{}-{}'.format(io_group,io_channel,chip_id))
        elif subnetwork['miso_us'].in_edges(chip_id):
            try:
                for link in subnetwork['miso_us'].in_edges(chip_id):
                    other_chip_id = link[0]
                    other_spec = [spec for spec in hydra_network_nodes if spec['chip_id'] == other_chip_id][0]
                    uart = None
                    if mapping_spec == 'old':
                        uart = node['miso_ds_uart_map'][other_spec['miso_us'].index(chip_id)]
                    elif mapping_spec == 'new':
                        uart = node['miso_uart_map'][other_spec['usds_link_map'][other_spec['miso_us'].index(chip_id)]]
                    link = (chip_id, other_chip_id)
                    self.add_network_link(io_group, io_channel, 'miso_ds', link, uart)
            except KeyError:
                raise KeyError('error auto-generating downstream network node {}-{}-{}'.format(io_group,io_channel,chip_id))

    def _link_mosi_network_node(self, io_group, io_channel, node, hydra_network_nodes, mapping_spec):
        chip_id = node['chip_id']
        subnetwork = self.network[io_group][io_channel]

        if 'mosi' in node:
            try:
                for idx, uart in enumerate(node['mosi_uart_map']):
                    link = (node['mosi'][idx], chip_id)
                    if link[1] is None: continue
                    self.add_network_link(io_group, io_channel, 'mosi', link, uart)
            except KeyError:
                raise KeyError('mosi_uart_map unspecified for {}-{}-{}'.format(io_group,io_channel,chip_id))
        elif subnetwork['miso_us'].in_edges(chip_id) or subnetwork['miso_ds'].in_edges(chip_id):
            try:
                # create links for existing miso_us connections
                if subnetwork['miso_us'].in_edges(chip_id):
                    for link in subnetwork['miso_us'].in_edges(chip_id):
                        other_chip_id = link[0]
                        other_spec = [spec for spec in hydra_network_nodes if spec['chip_id'] == other_chip_id][0]
                        uart = None
                        if mapping_spec == 'old':
                            uart = node['mosi_uart_map'][other_spec['miso_us'].index(chip_id)]
                        elif mapping_spec == 'new':
                            uart = node['mosi_uart_map'][other_spec['usds_link_map'][other_spec['miso_us'].index(chip_id)]]
                        link = (other_chip_id, chip_id)
                        self.add_network_link(io_group, io_channel, 'mosi', link, uart)

                # create links for existing miso_ds connections
                if subnetwork['miso_ds'].in_edges(chip_id):
                    for link in subnetwork['miso_ds'].in_edges(chip_id):
                        other_chip_id = link[0]
                        other_spec = [spec for spec in hydra_network_nodes if spec['chip_id'] == other_chip_id][0]
                        uart = None
                        if 'miso_ds' in other_spec:
                            if mapping_spec == 'old':
                                uart = node['mosi_uart_map'][other_spec['miso_ds'].index(chip_id)]
                            elif mapping_spec == 'new':
                                uart = node['mosi_uart_map'][other_spec['usds_link_map'][other_spec['miso_ds'].index(chip_id)]]
                        else:
                            # look up via ds uart channel map
                            ds_uart = subnetwork['miso_ds'].edges[link]['uart']
                            if mapping_spec == 'old':
                                uart = node['mosi_uart_map'][node['miso_us_uart_map'].index(ds_uart)]
                            elif mapping_spec == 'new':
                                uart = node['mosi_uart_map'][other_spec['usds_link_map'][node['miso_uart_map'].index(ds_uart)]]
                        link = (other_chip_id, chip_id)
                        self.add_network_link(io_group, io_channel, 'mosi', link, uart)
            except KeyError:
                raise KeyError('mosi_uart_map unspecified for {}-{}-{}'.format(io_group,io_channel,chip_id))

    def load_network(self, filename, version=2):
        '''
        Loads the specified file using the hydra io network configuration format
        with either a miso_us_uart_map/miso_ds_uart_map/mosi_uart_map specification
        or a miso_uart_map/mosi_uart_map/usds_uart_map specification.

        After loading the network, running
        ``controller.init_network(<io group>, <io channel>)`` will configure the
        chips with specified chip ids in the order declared in file

        :param filename: File path to configuration file

        '''
        system_info = configs.load(filename)
        inherited_data = tuple()
        old_style_inherited_data = ('miso_us_uart_map', 'miso_ds_uart_map', 'mosi_uart_map')
        new_style_inherited_data = ('miso_uart_map', 'mosi_uart_map', 'usds_link_map')
        mapping_spec = None
        if all([key in system_info['network'].keys() for key in old_style_inherited_data]):
            inherited_data = old_style_inherited_data
            mapping_spec = 'old'
        elif all([key in system_info['network'].keys() for key in new_style_inherited_data]):
            inherited_data = new_style_inherited_data
            mapping_spec = 'new'
        else:
            raise RuntimeError('uart mapping specification missing or invalid')

        orig_chips = copy(self.chips)
        orig_network = copy(self.network)
        # clear chips and network
        for chip in copy(self.chips):
            self.remove_chip(chip)
        for network_name in self.network_names:
            for io_group, io_channels in self.network.items():
                for io_channel, hydra_network in io_channels.items():
                    for node in hydra_network[network_name]:
                        self.network[io_group][io_channel][network_name].remove_node(node)
        try:
            self.chips = OrderedDict()
            full_network_spec = self._propogate_inherited_values(system_info['network'], inherited_data)

            # create nodes + chip objects first
            for key, group_spec in full_network_spec.items():
                if key in inherited_data: continue
                for subkey, channel_spec in full_network_spec[key].items():
                    if subkey in inherited_data: continue
                    for node_spec in channel_spec['nodes']:
                        self._create_network_node(int(key), int(subkey), node_spec, version=version)

            # then create miso_us network
            for key, group_spec in full_network_spec.items():
                if key in inherited_data: continue
                for subkey, channel_spec in full_network_spec[key].items():
                    if subkey in inherited_data: continue
                    for node_spec in channel_spec['nodes']:
                        self._link_miso_us_network_node(int(key),int(subkey),node_spec,channel_spec['nodes'],mapping_spec)

            # then create miso_ds network
            for key, group_spec in full_network_spec.items():
                if key in inherited_data: continue
                for subkey, channel_spec in full_network_spec[key].items():
                    if subkey in inherited_data: continue
                    for node_spec in channel_spec['nodes']:
                        self._link_miso_ds_network_node(int(key),int(subkey),node_spec,channel_spec['nodes'],mapping_spec)

            # finally, create mosi network
            for key, group_spec in full_network_spec.items():
                if key in inherited_data: continue
                for subkey, channel_spec in full_network_spec[key].items():
                    if subkey in inherited_data: continue
                    for node_spec in channel_spec['nodes']:
                        self._link_mosi_network_node(int(key), int(subkey), node_spec, channel_spec['nodes'],mapping_spec)

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

    def _default_chip_id_generator(self, io_group, io_channel):
            attempts = 0
            reserved_ids = [255,0,1]
            existing_ids = reserved_ids + [id for id in self.get_network_ids(io_group, io_channel) if isinstance(id,int)]
            chip_id = (existing_ids[-1] + 1) % 256
            while chip_id in existing_ids:
                chip_id = (chip_id + 1) % 256
                attempts += 1
                if attempts > 256:
                    raise RuntimeError('All possible chip ids are taken on network {} {}!'.format(io_group, io_channel))
            return chip_id

    def grow_network(self, io_group, io_channel, chip_id,
        miso_uart_map=[3,0,1,2], mosi_uart_map=[0,1,2,3], usds_link_map=[2,3,0,1],
        chip_id_generator=_default_chip_id_generator, timeout=0.01,
        modify_mosi=False, differential=True, version=2
        ):
        '''
        Recurisve algorithm to auto-complete a network from a stub. It works by
        attempting to link to each available upstream node in succession, keeping links
        that are verified. Repeats on each newly generated node until no possible links
        remain.

        To use with a completely unconfigured network you must first configure
        the root node representing the control system::

            controller.add_network_node(io_group, io_channel, controller.network_names, 'ext', root=True)

        You can then grow the network from this stub::

            controller.grow_network(io_group, io_channel, 'ext')

        This algorithim is limited to a regular geometry defined by the same
        miso_uart_map/mosi_uart_map/usds_link_map for each chip.

        :param io_group: the io group designation for the network

        :param io_channel: the io channel designation for the network

        :param chip_id: the chip id of the chip to start growth from

        :param miso_uart_map: a length 4 iterable indicating the miso channel used to send data to a chip at position i relative to the active chip

        :param mosi_uart_map: a length 4 iterable indicating the mosi channel used to receive data from a chip at position i relative to the active chip

        :param usds_link_map: a length 4 iterable indicating the relative position of the active chip from the perspective of the chip at position i

        :param chip_id_generator: a function that takes a controller, io_group, and io_channel and returns a unique chip id for that network

        :param timeout: the time duration in seconds to wait for a response from each configured node

        :param modify_mosi: flag to configure each chip's mosi, if set to ``True`` algorithm will also write the mosi configuration when probing chips, this will almost certainly leave you with deaf nodes and is not what you want. Leave at default ``False``

        :param differential: ``True`` to also enable differential signalling

        :returns: the generated 'miso_us', 'miso_ds', and 'mosi' networks as a `dict`

        '''

        network = self.network[io_group][io_channel]
        curr_chip_id = chip_id
        next_chip_ids = list()
        for idx in range(4):
            # don't try existing links
            if miso_uart_map[idx] in [network['miso_us'].edges[edge]['uart'] for edge in network['miso_us'].out_edges(chip_id)]:
                continue

            # attempt to create next link
            next_chip_id = chip_id_generator(self, io_group, io_channel)
            next_chip_key = Key(io_group, io_channel, next_chip_id)
            self.add_chip(next_chip_key, version=version)
            self.add_network_link(io_group, io_channel, 'miso_us', (curr_chip_id, next_chip_id), miso_uart_map[idx])
            self.add_network_link(io_group, io_channel, 'miso_ds', (next_chip_id, curr_chip_id), miso_uart_map[usds_link_map[idx]])
            self.add_network_link(io_group, io_channel, 'mosi', (next_chip_id, curr_chip_id), mosi_uart_map[idx])
            self.add_network_link(io_group, io_channel, 'mosi', (curr_chip_id, next_chip_id), mosi_uart_map[usds_link_map[idx]])

            # configure link and verify
            ok,diff = self.init_network_and_verify(io_group, io_channel, next_chip_id, retries=0, timeout=timeout, modify_mosi=modify_mosi, differential=differential)
            if ok:
                next_chip_ids.append(next_chip_id)
            else:
                self.reset_network(io_group, io_channel, next_chip_id)
                self.remove_chip(next_chip_key)

        # repeat on child nodes
        for chip_id in next_chip_ids:
            self.grow_network(io_group, io_channel, chip_id, miso_uart_map=miso_uart_map, mosi_uart_map=mosi_uart_map, usds_link_map=usds_link_map, chip_id_generator=chip_id_generator, differential=differential, modify_mosi=modify_mosi, timeout=timeout)

        return network

    def init_network_and_verify(self, io_group=1, io_channel=1, chip_id=None, timeout=0.2, retries=10, modify_mosi=True, differential=True):
        '''
        Runs init network, verifying that registers are updated properly at each step
        Will exit if any chip network configuration cannot be set correctly after
        ``retries`` attempts

        '''
        if chip_id is None:
            chip_ids = self.get_network_ids(io_group, io_channel, root_first_traversal=True)
            for chip_id in chip_ids:
                ok,diff = self.init_network_and_verify(io_group, io_channel, chip_id=chip_id, timeout=timeout, retries=retries, modify_mosi=modify_mosi, differential=differential)
                if not ok:
                    return ok,diff
            return ok,dict()

        keys_to_verify = list()
        if isinstance(chip_id,int):
            keys_to_verify.append(Key(io_group,io_channel,chip_id))
        for us_link in self.network[io_group][io_channel]['miso_us'].in_edges(chip_id):
            if not isinstance(us_link[0], int):
                continue
            parent_chip_id = us_link[0]
            keys_to_verify.append(Key(io_group, io_channel, parent_chip_id))

        if not keys_to_verify:
            return True,dict()
        print('init',io_group,io_channel,chip_id)
        self.init_network(io_group, io_channel, chip_id, modify_mosi=modify_mosi, differential=differential)
        ok,diff = self.verify_network(keys_to_verify, timeout=timeout)
        for _ in range(retries):
            if ok: return ok,diff
            for chip_key in diff:
                self.write_configuration(chip_key, diff[chip_key].keys())
            ok,diff = self.verify_registers([
                (chip_key, list(diff[chip_key].keys())) for chip_key in diff
            ])
        if not ok:
            print('Failed to verify network nodes {}'.format(diff.keys()))
        return ok,diff

    def init_network(self, io_group=1, io_channel=1, chip_id=None, modify_mosi=True, differential=True):
        '''
        Configure a Hydra io node specified by chip_id, if none are specified,
        load complete network
        To configure a Hydra io network, the following steps are followed:

         - Enable miso_us of parent chip
         - Enable mosi of parent chip
         - Write chip_id to chip on io group + io channel (assuming chip id 1)
         - Write enable_miso_downstream to chip chip_id (also enable differential if desired)
         - Write enable_mosi to chip chip_id (optional)

        '''
        subnetwork = self.network[io_group][io_channel]
        if chip_id is None:
            chip_ids = self.get_network_ids(io_group, io_channel, root_first_traversal=True)
            for chip_id in chip_ids:
                self.init_network(io_group, io_channel, chip_id=chip_id, modify_mosi=modify_mosi, differential=differential)
            return

        packets = []
        chip_key = None
        if isinstance(chip_id, int):
            chip_key = Key(io_group, io_channel, chip_id)

        # Enable miso_upstream on parent chips
        for us_link in subnetwork['miso_us'].in_edges(chip_id):
            if not isinstance(us_link[0], int):
                continue
            parent_chip_id = us_link[0]
            parent_chip_key = Key(io_group, io_channel, parent_chip_id)
            parent_uart = subnetwork['miso_us'].edges[us_link]['uart']
            self[parent_chip_key].config.enable_miso_upstream[parent_uart] = 1
            packets += self[parent_chip_key].get_configuration_write_packets(registers=self[parent_chip_key].config.register_map['enable_miso_upstream'])

            for mosi_link in subnetwork['mosi'].in_edges(parent_chip_id):
                mosi_uart = subnetwork['mosi'].edges[mosi_link]['uart']
                if not self[parent_chip_key].config.enable_mosi[mosi_uart]:
                    self[parent_chip_key].config.enable_mosi[mosi_uart] = 1
                    packets += self[parent_chip_key].get_configuration_write_packets(registers=self[parent_chip_key].config.register_map['enable_mosi'])

        if chip_key:
            # Only modify chip configuration if node points to a chip object

            # Write chip_id to specified chip
            self[chip_key].config.chip_id = chip_key.chip_id
            packets += self[chip_key].get_configuration_write_packets(registers=self[chip_key].config.register_map['chip_id'])
            packets[-1].chip_id = 1

            # Enable miso_downstream, mosi on chip
            if differential:
                self[chip_key].config.enable_miso_differential = [1]*4

            self[chip_key].config.enable_miso_downstream = [0]*4
            for ds_link in subnetwork['miso_ds'].out_edges(chip_id):
                ds_uart = subnetwork['miso_ds'].edges[ds_link]['uart']
                self[chip_key].config.enable_miso_downstream[ds_uart] = 1
            packets += self[chip_key].get_configuration_write_packets(registers=self[chip_key].config.register_map['enable_miso_downstream'])

            if modify_mosi:
                self[chip_key].config.enable_mosi = [0]*4
                for mosi_link in subnetwork['mosi'].in_edges(chip_id):
                    mosi_uart = subnetwork['mosi'].edges[mosi_link]['uart']
                    self[chip_key].config.enable_mosi[mosi_uart] = 1
                packets += self[chip_key].get_configuration_write_packets(registers=self[chip_key].config.register_map['enable_mosi'])

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
            chip_keys = self.get_network_keys(io_group, io_channel, root_first_traversal=False)
            for chip_key in chip_keys:
                self.reset_network(io_group, io_channel, chip_id=chip_key.chip_id)
            return

        packets = []
        chip_key = None
        if isinstance(chip_id, int):
            # Only modify chip configuration if node points to a chip object
            chip_key = Key(io_group, io_channel, chip_id)

            # Enable mosi
            self[chip_key].config.enable_mosi = [1]*4
            packets += self[chip_key].get_configuration_write_packets(registers=self[chip_key].config.register_map['enable_mosi'])

            # Disable miso_downstream
            self[chip_key].config.enable_miso_downstream = [0]*4
            packets += self[chip_key].get_configuration_write_packets(registers=self[chip_key].config.register_map['enable_miso_downstream'])

            # Write default chip_id to specified chip
            self[chip_key].config.chip_id = 1
            packets += self[chip_key].get_configuration_write_packets(registers=self[chip_key].config.register_map['chip_id'])

        # Disable miso_upstream on parent chips
        for us_link in subnetwork['miso_us'].in_edges(chip_id):
            if not isinstance(us_link[0], int):
                continue
            parent_chip_id = us_link[0]
            parent_chip_key = Key(io_group, io_channel, parent_chip_id)
            parent_uart = subnetwork['miso_us'].edges[us_link]['uart']
            self[parent_chip_key].config.enable_miso_upstream[parent_uart] = 0
            packets += self[parent_chip_key].get_configuration_write_packets(registers=self[chip_key].config.register_map['enable_miso_upstream'])

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
                            message=None, connection_delay=0.2):
        '''
        Send the configurations stored in chip.config to the LArPix
        ASIC.

        By default, sends all registers. If registers is an int, then
        only that register is sent. If registers is a string, then
        the sent registers will set by looking at the configuration
        register map. If registers is an iterable, then
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
        elif isinstance(registers, str):
            registers = list(chip.config.register_map[registers])
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
            time.sleep(connection_delay)
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
                           message=None, connection_delay=0.2):
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
        elif isinstance(registers, str):
            registers = chip.config.register_map[registers]
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
            time.sleep(connection_delay)
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
                                  message=None, connection_delay=0.2):
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
            time.sleep(connection_delay)
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
                                 message=None, connection_delay=0.2):
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
            time.sleep(connection_delay)
            stop_time = time.time() + timeout
        self.send(packets)
        if not already_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
        packets, bytestream = self.read()
        self.stop_listening()
        self.store_packets(packets, bytestream, message)

    def run(self, timelimit, message):
        '''
        Read data from the LArPix ASICs for the given ``timelimit`` and
        associate the received Packets with the given ``message``.

        '''
        sleeptime = min(0.1, timelimit)
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

    def verify_registers(self, chip_key_register_pairs, timeout=1, connection_delay=0.02, n=1):
        '''
        Read chip configuration from specified chip and registers and return ``True`` if the
        read chip configuration matches the current configuration stored in chip instance.

        :param chip_key_register_pair: a ``list`` of key register pairs as documented in ``controller.multi_read_configuration``

        :param timeout: set how long to wait for response in seconds (optional)

        :param n: sets maximum recursion depth, will continue to attempt to verify registers until this depth is reached or all registers have responded, a value <1 allows for infinite recursion (optional)

        :returns: 2-``tuple`` of a ``bool`` representing if all registers match and a ``dict`` representing all differences. Differences are specified as ``{<chip_key>: {<register>: (<expected>, <read>)}}``

        '''
        return_value = True
        different_fields = {}
        registers = {}
        for chip_key, chip_registers in chip_key_register_pairs:
            if not isinstance(chip_registers, (list,tuple,range)):
                if chip_key in registers:
                    registers[chip_key] += [chip_registers]
                else:
                    registers[chip_key] = [chip_registers]
            else:
                if chip_key in registers:
                    registers[chip_key] += list(chip_registers)
                else:
                    registers[chip_key] = list(chip_registers)
        self.multi_read_configuration(chip_key_register_pairs, timeout=timeout, connection_delay=connection_delay)
        configuration_data = dict([
            (chip_key, dict([
                (register,(None, None))
                for register in chip_registers]))
            for chip_key, chip_registers in registers.items()])
        for packet in self.reads[-1]:
            packet_key = packet.chip_key
            if (hasattr(packet,'CONFIG_READ_PACKET') and packet.packet_type == packet.CONFIG_READ_PACKET):
                register_address = packet.register_address
                if packet_key in configuration_data and register_address in configuration_data[packet_key]:
                    configuration_data[packet_key][register_address] = (None, packet.register_data)

        for chip_key in registers.keys():
            expected_data = dict()
            if self[chip_key].asic_version == 1:
                expected_data = dict([(register_address, bah.touint(bits)) for register_address, bits in enumerate(self[chip_key].config.all_data())])
            else:
                expected_data = dict([(register_address, bah.touint(bits, endian=Packet_v2.endian)) for register_address, bits in enumerate(self[chip_key].config.all_data())])

            for register in set(registers[chip_key]):
                configuration_data[chip_key][register] = (expected_data[register], configuration_data[chip_key][register][1])
                if not configuration_data[chip_key][register][0] == configuration_data[chip_key][register][1]:
                    return_value = False
                else:
                    del configuration_data[chip_key][register]
            if not len(configuration_data[chip_key]):
                del configuration_data[chip_key]

        if not return_value and n != 1:
            retry_chip_key_register_pairs = [(key,register) for key,value in configuration_data.items() for register in value if value[register][-1] is None]
            if len(retry_chip_key_register_pairs):
                retry_return_value, retry_configuration_data = self.verify_registers(
                    retry_chip_key_register_pairs,
                    timeout=timeout,
                    connection_delay=connection_delay,
                    n=n-1
                    )
                for chip_key in retry_configuration_data.keys():
                    configuration_data[chip_key].update(retry_configuration_data[chip_key])
                for chip_key,register in retry_chip_key_register_pairs:
                    if chip_key not in retry_configuration_data or register not in retry_configuration_data[chip_key]:
                        del configuration_data[chip_key][register]
                return_value = all([
                    configuration_data[chip_key][register][0] == configuration_data[chip_key][register][1]
                    for chip_key in configuration_data
                    for register in configuration_data[chip_key]
                    ])
        return (return_value, configuration_data)

    def verify_configuration(self, chip_keys=None, timeout=1, connection_delay=0.02, n=1):
        '''
        Read chip configuration from specified chip(s) and return ``True`` if the
        read chip configuration matches the current configuration stored in chip instance.
        ``chip_keys`` can be a single chip key, a list of chip keys, or ``None``. If
        ``chip_keys`` is ``None`` all chips will be verified.

        Also returns a dict containing the values of registers that are different
        (read register, stored register)

        :param chip_keys: ``list`` of chip_keys to verify

        :param timeout: how long to wait for response in seconds

        :param n: set recursion limit for rechecking non-responding registers

        :returns: 2-``tuple`` with same format as ``controller.verify_registers``

        '''
        if chip_keys is None:
            chip_keys = self.chips.keys()
        if isinstance(chip_keys,(str,Key)):
            chip_keys = [chip_keys]
        chip_key_register_pairs = [(chip_key, range(self[chip_key].config.num_registers)) for chip_key in chip_keys]
        return self.verify_registers(chip_key_register_pairs, timeout=timeout, connection_delay=connection_delay, n=n)

    def verify_network(self, chip_keys=None, timeout=1):
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
        chip_key_register_pairs = [
            (chip_key, list(self[chip_key].config.register_map['chip_id']) + \
            list(self[chip_key].config.register_map['enable_mosi']) + \
            list(self[chip_key].config.register_map['enable_miso_upstream']) + \
            list(self[chip_key].config.register_map['enable_miso_downstream']) + \
            list(self[chip_key].config.register_map['enable_miso_differential']))
            for chip_key in chip_keys]
        return self.verify_registers(chip_key_register_pairs)

    def enforce_registers(self, chip_key_register_pairs, timeout=1, connection_delay=0.02, n=1, n_verify=1):
        '''
        Read chip configuration from specified chip and registers and write registers to
        read chip configurations that do not match the current configuration stored in chip instance.

        :param chip_key_register_pair: a ``list`` of key register pairs as documented in ``controller.multi_read_configuration``

        :param timeout: set how long to wait for response in seconds (optional)

        :param n: sets maximum recursion depth, will continue to attempt to enforce registers until this depth is reached or all registers have responded, a value <1 allows for infinite recursion (optional)

        :param n_verify: maximum recursion depth for verify registers (optional)

        :returns: 2-``tuple`` with same format as ``controller.verify_registers``

        '''
        ok,diff = self.verify_registers(chip_key_register_pairs, timeout=timeout, connection_delay=connection_delay, n=n_verify)
        if not ok:
            chip_key_register_pairs = [
                (chip_key, register)
                for chip_key in diff
                for register in diff[chip_key]
                ]
            self.multi_write_configuration(chip_key_register_pairs, write_read=0, connection_delay=connection_delay)
            if n != 1:
                ok,diff = self.enforce_registers(chip_key_register_pairs, timeout=timeout, connection_delay=connection_delay, n=n-1, n_verify=n_verify)
            else:
                ok,diff = self.verify_registers(chip_key_register_pairs, timeout=timeout, connection_delay=connection_delay, n=n_verify)
        return ok,diff

    def enforce_configuration(self, chip_keys=None, timeout=1, connection_delay=0.02, n=1, n_verify=1):
        '''
        Read chip configuration from specified chip(s) and write registers to
        read chip configuration that do not match the current configuration stored in chip instance.
        ``chip_keys`` can be a single chip key, a list of chip keys, or ``None``. If
        ``chip_keys`` is ``None`` all chip configs will be enforced.

        Also returns a dict containing the values of registers that are different
        (read register, stored register)

        :param chip_keys: ``list`` of chip_keys to verify

        :param timeout: how long to wait for response in seconds

        :param n: set recursion limit for enforcing non-matching registers (optional)

        :param n_verify: set recursion limit for verifying registers (optional)

        :returns: 2-``tuple`` with same format as ``controller.verify_registers``

        '''
        if chip_keys is None:
            chip_keys = self.chips.keys()
        if isinstance(chip_keys,(str,Key)):
            chip_keys = [chip_keys]
        chip_key_register_pairs = [(chip_key, range(self[chip_key].config.num_registers)) for chip_key in chip_keys]
        return self.enforce_registers(chip_key_register_pairs, timeout=timeout, connection_delay=connection_delay, n=n, n_verify=n_verify)

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
        elif chip.asic_version in (2, 'lightpix-1'):
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
                self.disable_analog_monitor(chip_key=chip, channel=channel)
        else:
            chip = self[chip_key]
            if chip.asic_version == 1:
                chip.config.disable_analog_monitor()
                self.write_configuration(chip_key, chip.config.csa_monitor_select_addresses)
            elif chip.asic_version in (2, 'lightpix-1'):
                if not channel is None:
                    chip.config.csa_monitor_select[channel] = 0
                else:
                    chip.config.csa_monitor_select = [0]*64
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
        elif chip.asic_version in (2, 'lightpix-1'):
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
        elif chip.asic_version in (2, 'lightpix-1'):
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
                self.write_configuration(chip_key, chip.config.csa_testpulse_enable_addresses)
            elif chip.asic_version in (2, 'lightpix-1'):
                for channel in channel_list:
                    chip.config.csa_testpulse_enable[channel] = 1
                self.write_configuration(chip_key, chip.config.register_map['csa_testpulse_enable'])
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
            elif chip.asic_version in (2, 'lightpix-1'):
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
            elif chip.asic_version in (2, 'lightpix-1'):
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
