'''
Generate a simple Hydra io network for specified io channels and io groups.
In this case, a 'simple' network applies the following constraints on the network:

     - All configuration packets originate at one point (head) and all data packets
     are returned via the same point
     - Hydra nodes are arranged in a regular grid, i.e. left 1, down 1 == down 1, left 1
     - Each uart is configured s.t. mosi[i] == miso_ds[i] or miso_us[i]
     - Neighboring nodes are configured s.t. miso_us[i] == mosi[j] with j being the connected
     port to i (e.g. 0<->2 and 1<->3)

'''

import numpy as np
import networkx as nx
from bidict import bidict
import random

default_miso_us_uart_map = [0,1,2,3]
default_miso_ds_uart_map = [2,3,0,1]
default_mosi_uart_map = [0,1,2,3]
uart_us_table = bidict({
    (0,1): 0,
    (1,0): 3,
    (-1,0): 1,
    (0,-1): 2
    })
uart_ds_table = bidict({
    (0,-1): 0,
    (-1,0): 3,
    (1,0): 1,
    (0,1): 2
    })

def edge_dir(edge):
    dx = edge[1][0] - edge[0][0]
    dy = edge[1][1] - edge[0][1]
    return (dx, dy)

def chip_id_simple(g, position):
    '''
    Generates an easy-to-read chip id based on the position (excluding 0, 1, and 255)
    Chip ids increase by increments of 1 at each node position in y and 10 at each
    node position in x (works for max of 8x8 grid)

    '''
    return (position[0]*10 + position[1]) % 253 + 2

def chip_id_position(g, position):
    '''
    Generates a chip id based on the position excluding ids 0, 1, and 255
    Chip id increase by increments of 1 at each node position in y dimension
    Chip ids are only guaranteed to be unique if less than 253 positions in
    rectangle bounding all nodes

    '''
    max_pos = max(g.nodes())
    min_pos = min(g.nodes())
    id_factor = max_pos[1] - min_pos[1] + 1
    return (position[0]*id_factor + position[1]) % 253 + 2

def chip_id_head(g, node, root=None):
    '''
    Generates a chip id based on the distance from the source node
    Guarantees unique chip ids as long as there are less than 253 nodes in graph

    '''
    distance = 0
    if not root:
        root = [curr_node for curr_node in g.nodes() if g.in_degree(curr_node) == 0]
    nodes = [root]
    while nodes:
        for curr_node in nodes:
            if curr_node == node:
                return distance % 253 + 2
            distance += 1
        nodes = [edge[1] for edge in g.edges(nodes)]

def generate_chip_id_simple(g, method='chip_id_simple'):
    '''
    Generates a ``chip_id`` field on each node based a dedicated scheme

    '''
    for node in g.nodes():
        if 'chip_id' in g.node[node]:
            continue
        g.node[node]['chip_id'] = globals()[method](g, node)

def generate_hydra_simple_digraphs(x_slots, y_slots, root, ext, avoid=None, seed=12345):
    '''
    Generates a "simple" hydra io networks.

    In addition to insuring the "simple" contraints, algorithm aims to produce a
    network with balanced branches (i.e. each upstream uart on a node should have
    roughly equal numbers of successive nodes). This helps to insure that the data load on any given
    uart is about the same. There is not a unique solution and so a random seed
    is used to generate the network

    :param x_slots: maximum number of x positions for nodes

    :param y_slots: maximum number of y positions for nodes

    :param root: ``(x,y)`` position for root node, ``0 <= x < x_slots``, ``0 <= y < y_slots``

    :param ext: position of the node representing the external system

    :param avoid: ``list`` of ``(x,y)`` nodes to exclude from network

    :param seed: random seed for configuration (insures repeatabilty)

    :returns: 3 networkx ``DiGraph``s indicating the upstream miso network, the downstream miso network, and the mosi network

    '''
    random.seed(seed)

    g_us = nx.grid_2d_graph(x_slots, y_slots, create_using=nx.DiGraph) # base graph for upstream
    g_us.add_node(ext)

    if avoid:
        g_us.remove_nodes_from(avoid)

    # create root
    g_us.nodes[root]['root'] = True
    g_us.nodes[ext]['chip_id'] = 'ext'
    g_us.remove_edges_from(list(g_us.in_edges(root)))
    g_us.add_edge(ext, root)

    # remove in edges from each successor
    nodes = list(g_us.successors(root))
    while nodes:
        random.shuffle(nodes)
        edges_to_remove = [edge for edge in g_us.in_edges(nodes) \
            if edge[::-1] in g_us.out_edges(nodes) \
            and g_us.in_degree(edge[1]) > 1]
        g_us.remove_edges_from(edges_to_remove)
        nodes = [edge[1] for edge in g_us.edges(nodes)]

    # work forward from root node pruning out degrees that link to most
    # successors (each node independently tries to minimize upstream nodes)
    nodes = [node for node in g_us.nodes() if g_us.in_degree(node) > 1]
    while nodes:
        edges = list(g_us.in_edges(nodes))
        random.shuffle(edges)
        edge1_children = [len(nx.dfs_successors(g_us, edge[1])) for edge in edges]
        edge0_children = [len(nx.dfs_successors(g_us, edge[0])) for edge in edges]
        metric = [n1 + (n0-n1) for n0, n1 in zip(edge0_children, edge1_children)]
        g_us.remove_edge(*edges[np.argmax(metric)])
        nodes = [node for node in g_us.nodes() if g_us.in_degree(node) > 1]

    # generate downstream miso
    g_ds = nx.DiGraph()
    g_ds.add_nodes_from(g_us.nodes())
    g_ds.add_edges_from([(edge[::-1]) for edge in g_us.edges()])
    g_ds.nodes[root]['root'] = True
    g_ds.nodes[ext]['chip_id'] = 'ext'

    # generate mosi
    g_mosi = nx.DiGraph()
    g_mosi.add_nodes_from(g_us.nodes())
    g_mosi.add_edges_from(g_us.edges())
    g_mosi.add_edges_from(g_ds.edges())
    g_mosi.nodes[root]['root'] = True
    g_mosi.nodes[ext]['chip_id'] = 'ext'

    return g_us, g_ds, g_mosi

def generate_network_config(network_graphs, io_group, io_channel, name=None, previous=None):
    '''
    Converts a hydra network configuration graph into a json-encodable dict
    conforming to the Controller network configuration specification

    :param network_graphs: 3-tuple of networkx graph objects representing the miso_us, miso_ds, and mosi networks. Each node must have ``'chip_id'`` fields

    :param io_group: The io group for this hydra network

    :param io_channel: This io channel for this hydra network

    :param name: Name of configuration, default is ``max(nodes)``

    :param previous: A dict conforming to the Controller network configuration specification to add/overwrite

    :returns: json-ready ``dict`` conforming to Controller network configuration specification

    '''
    g = network_graphs[0] # upstream (convienence handle)
    network_config = {
        'name': '{}'.format(max(g.nodes())),
        'type': 'network',
        'network': {}
        }
    if previous:
        network_config = previous
    if name:
        network_config['name'] = name
    io_group, io_channel = str(io_group), str(io_channel)
    if not io_group in network_config['network']:
        network_config['network'][io_group] = dict()
    if not io_channel in network_config['network'][io_group]:
        network_config['network'][io_group][io_channel] = dict()
    network_config['network'][io_group][io_channel]['chips'] = []

    if not 'miso_us_uart_map' in network_config['network']:
        network_config['network']['miso_us_uart_map'] = default_miso_us_uart_map
    if not 'miso_ds_uart_map' in network_config['network']:
        network_config['network']['miso_ds_uart_map'] = default_miso_ds_uart_map
    if not 'mosi_uart_map' in network_config['network']:
        network_config['network']['mosi_uart_map'] = default_mosi_uart_map

    subnetwork = network_config['network'][io_group][io_channel]
    if not default_miso_us_uart_map == network_config['network']['miso_us_uart_map']:
        subnetwork['miso_us_uart_map'] = default_miso_us_uart_map
    if not default_miso_ds_uart_map == network_config['network']['miso_ds_uart_map']:
        subnetwork['miso_ds_uart_map'] = default_miso_ds_uart_map
    if not default_mosi_uart_map == network_config['network']['mosi_uart_map']:
        subnetwork['mosi_uart_map'] = default_mosi_uart_map

    next_nodes = [node for node in g.nodes() if g.in_degree(node) < 1]
    while next_nodes:
        for node in next_nodes:
            if not isinstance(g.nodes[node]['chip_id'],int):
                continue
            subnetwork['chips'] += [{
                'chip_id': g.nodes[node]['chip_id'],
                'miso_us': [None]*4
                }]
            chip_config = subnetwork['chips'][-1]
            for child in g.successors(node):
                child_uart = uart_us_table[edge_dir((node,child))]
                chip_config['miso_us'][default_miso_us_uart_map.index(child_uart)] = g.nodes[child]['chip_id']
            if not any(chip_config['miso_us']):
                del chip_config['miso_us']
            if 'root' in g.nodes[node]:
                chip_config['root'] = True
                chip_config['miso_ds'] = [None]*4
                for parent in g.predecessors(node):
                    parent_uart = uart_ds_table[edge_dir((parent,node))]
                    chip_config['miso_ds'][default_miso_ds_uart_map.index(parent_uart)] = g.nodes[parent]['chip_id']
        next_nodes = [edge[1] for edge in g.out_edges(next_nodes)]
    return network_config

def plot(g, name='figure', labels=True):
    '''
    Draws a network configuration graph (using matplotlib)

    :param g: A networkx graph object representing the configuration, each node must be a 2-``tuple`` with a ``'chip_id'`` field

    '''
    import matplotlib.pyplot as plt
    plt.ion()
    plt.figure(name)
    if labels:
        nx.draw_networkx(g, dict([(node,node) for node in g.nodes]), labels=dict([(node,g.nodes[node]['chip_id']) for node in g.nodes]))
    else:
        nx.draw_networkx(g, dict([(node,node) for node in g.nodes]))

if __name__ == '__main__':
    import argparse
    import os
    import json

    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument('--outfile', '-o', type=str, required=False, default=None,
        help='''
        output filename (optional, default=<name>.json)
        if file exists, io groups / io channels will be added to existing file
        ''')
    parser.add_argument('--name', '-n', type=str, required=True, help='''
        configuration name (required)
        ''')
    parser.add_argument('--seed', '-s', type=int, required=False, default=12345, help='''
        seed for random shuffles
        ''')
    parser.add_argument('--x_slots', '-x', type=int, required=True, help='''
        max number of slots for network nodes (in x dim)
        ''')
    parser.add_argument('--y_slots', '-y', type=int, required=True, help='''
        max number of slots for network nodes (in y dim)
        ''')
    parser.add_argument('--root', '-r', type=int, required=True, nargs=2, help='''
        position for root node
        ''')
    parser.add_argument('--ext', '-e', type=int, required=True, nargs=2, help='''
        position for external placeholder node
        ''')
    parser.add_argument('--avoid', type=int, required=False, default=[], nargs='+', help='''
        positions of nodes to avoid, specified as unified list of x, y positions
        (even idexes are x positions, odd are y positions)
        ''')
    parser.add_argument('--chip_id', type=str, required=False, default='chip_id_simple',
        help='''sets method for generating and assigning chip ids, options are
        'chip_id_simple', 'chip_id_position', and 'chip_id_head'
        ''')
    parser.add_argument('--io_group', type=int, required=False, default=1,
        help='''sets io group'
        ''')
    parser.add_argument('--io_channel', type=int, required=False, default=1,
        help='''sets io channel'
        ''')
    parser.add_argument('--plot', action='store_true', help='''
        flag to plot network instead of generating file
        ''')

    args = parser.parse_args()
    avoid = [(int(args.avoid[i]), int(args.avoid[i+1])) for i in range(0,len(args.avoid),2)]
    g_us, g_ds, g_mosi = generate_hydra_simple_digraphs(args.x_slots,
        args.y_slots, tuple(args.root), tuple(args.ext), avoid=avoid, seed=args.seed)
    generate_chip_id_simple(g_us, method=args.chip_id) # add chip ids to each node
    generate_chip_id_simple(g_ds, method=args.chip_id) # add chip ids to each node
    generate_chip_id_simple(g_mosi, method=args.chip_id) # add chip ids to each node

    if args.plot:
        plot(g_us, name='MISO upstream')
        plot(g_ds, name='MISO downstream')
        plot(g_mosi, name='MOSI')
        print('Press enter to quit')
        input()
        exit()

    previous_config = None
    if os.path.exists(args.outfile):
        with open(args.outfile,'r') as f:
            previous_config = json.load(f)
    new_config = generate_network_config((g_us, g_ds, g_mosi), args.io_group, args.io_channel, name=args.name, previous=previous_config)
    with open(args.outfile,'w') as f:
        json.dump(new_config, f, indent=4)
