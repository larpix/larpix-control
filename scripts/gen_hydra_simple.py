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
from copy import deepcopy

default_miso_uart_map = [3,0,1,2]
default_mosi_uart_map = [0,1,2,3]
default_usds_link_map = [2,3,0,1]
dir_table = bidict({
    (0,1): 0,
    (1,0): 3,
    (-1,0): 1,
    (0,-1): 2
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

def generate_chip_id(g, method='chip_id_simple'):
    '''
    Generates a ``chip_id`` field on each node based a dedicated scheme

    '''
    for node in g.nodes():
        if 'chip_id' in g.nodes[node]:
            continue
        g.nodes[node]['chip_id'] = globals()[method](g, node)

def generate_digraphs_from_upstream(g, root, ext):
    '''
    Generate g_us, g_ds, g_mosi assuming g is a directed graph of the upstream
    network with root node ``root`` and an external node ``ext``

    :returns: tuple of g_us, g_ds, g_mosi

    '''
    # generate upstream miso
    g_us = nx.DiGraph()
    g_us.add_nodes_from(g.nodes())
    g_us.add_edges_from([edge for edge in g.edges()])
    g_us.nodes[root]['root'] = True
    g_us.nodes[ext]['chip_id'] = 'ext'

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

def generate_2d_grid_digraph(x_slots, y_slots, *args):
    g = nx.grid_2d_graph(x_slots, y_slots, create_using=nx.DiGraph)
    for node in args:
        g.add_node(node)
    for x in range(-1,2):
        for y in range(-1,2):
            if abs(x) + abs(y) == 1:
                for node in args:
                    if (node[0]+x,node[1]+y) in g.nodes():
                        g.add_edge(node,(node[0]+x,node[1]+y))
                        g.add_edge((node[0]+x,node[1]+y),node)
    return g

def generate_hydra_simple_digraphs(x_slots, y_slots, root, ext, avoid=None, seed=12345):
    '''
    Generates a simple hydra io networks using the simple algorithm. Roughly,
    this algorithm generates a simple hydra io network based on an upstream
    network. The upstream network is found by this algorithm:

        1. create network with all connections to neighbors

        2. starting at root node, prune all incoming connections that also have an outgoing connection

        3. iteratively prune connection with the largest n_children[head] + n_children[tail]

    There is not a unique solution and so a random seed is used to generate the network

    :param x_slots: maximum number of x positions for nodes

    :param y_slots: maximum number of y positions for nodes

    :param root: ``(x,y)`` position for root node, ``0 <= x < x_slots``, ``0 <= y < y_slots``

    :param ext: position of the node representing the external system

    :param avoid: ``list`` of ``(x,y)`` nodes to exclude from network

    :param seed: random seed for configuration (insures repeatabilty)

    :returns: 3 networkx ``DiGraph``s indicating the upstream miso network, the downstream miso network, and the mosi network

    '''
    random.seed(seed)

    g = generate_2d_grid_digraph(x_slots, y_slots, root, ext)
    #    g = nx.grid_2d_graph(x_slots, y_slots, create_using=nx.DiGraph) # base graph for upstream

    if avoid:
        g.remove_nodes_from(avoid)

    # create root
    g.remove_edges_from(list(g.in_edges(root)))

    # remove in edges from each successor
    nodes = list(g.successors(root))
    while nodes:
        random.shuffle(nodes)
        edges_to_remove = [edge for edge in g.in_edges(nodes) \
            if edge[::-1] in g.out_edges(nodes) \
            and g.in_degree(edge[1]) > 1]
        g.remove_edges_from(edges_to_remove)
        nodes = list(set([edge[1] for edge in g.out_edges(nodes)]))

    # work forward from root node pruning out links that contribute to nodes
    # with largest fifo load
    nodes = [node for node in g.nodes() if g.in_degree(node) > 1]
    while nodes:
        edges = list(g.in_edges(nodes))
        random.shuffle(edges)

        metric = [len(nx.descendants(g, edge[1])) + len(nx.descendants(g, edge[0])) for edge in edges]
        g.remove_edge(*edges[np.argmax(metric)])
        nodes = [node for node in g.nodes() if g.in_degree(node) > 1]

    return generate_digraphs_from_upstream(g, root, ext)

def generate_hydra_simple2_digraphs(x_slots, y_slots, root, ext, avoid=None, seed=12345):
    '''
    Generates a simple hydra io networks using the simple2 algorithm. Roughly,
    this algorithm generates a simple hydra io network based on an upstream
    network. The upstream network is found in the same way as the simple algorithm
    except the score metric is the connection with the fewest children.

    This generally performs the best of all the algorithms developed.

    There is not a unique solution and so a random seed is used to generate the network

    :param x_slots: maximum number of x positions for nodes

    :param y_slots: maximum number of y positions for nodes

    :param root: ``(x,y)`` position for root node, ``0 <= x < x_slots``, ``0 <= y < y_slots``

    :param ext: position of the node representing the external system

    :param avoid: ``list`` of ``(x,y)`` nodes to exclude from network

    :param seed: random seed for configuration (insures repeatabilty)

    :returns: 3 networkx ``DiGraph``s indicating the upstream miso network, the downstream miso network, and the mosi network

    '''
    random.seed(seed)

    g = generate_2d_grid_digraph(x_slots, y_slots, root, ext)
    #    g = nx.grid_2d_graph(x_slots, y_slots, create_using=nx.DiGraph) # base graph for upstream

    if avoid:
        g.remove_nodes_from(avoid)

    # create root
    g.remove_edges_from(list(g.in_edges(root)))

    # remove in edges from each successor
    nodes = list(g.successors(root))
    while nodes:
        random.shuffle(nodes)
        edges_to_remove = [edge for edge in g.in_edges(nodes) \
            if edge[::-1] in g.out_edges(nodes) \
            and g.in_degree(edge[1]) > 1]
        g.remove_edges_from(edges_to_remove)
        nodes = list(set([edge[1] for edge in g.out_edges(nodes)]))

    # get all redundant connections
    nodes = [node for node in g.nodes() if g.in_degree(node) > 1]
    while nodes:
        edges = list(g.in_edges(nodes))
        random.shuffle(edges)

        # get edge with least number of children
        edge_metric = sorted([(len(nx.descendants(g, edge[1])), edge) for edge in edges])
        g.remove_edge(*edge_metric[0][1])
        nodes = [node for node in g.nodes() if g.in_degree(node) > 1]

    return generate_digraphs_from_upstream(g, root, ext)

def L(i, d_in, n_us):
    '''
    Helper function for calculating fifo load, representing the increase in the
    fifo value during readout period ``i``. Maximum FIFO value can be found
    by summing from ``i=-1`` to ``i=d_in-1``, inclusive.

    :param i: iterator index

    :param d_in: in degree of node in downstream network

    :param n_us: sorted list of number of downstream parents of node (0 == least upstream children) of each connection in downstream network

    :returns: ``int``

    '''
    if i == -1:
        return 1
    if i == 0:
        return d_in - 1
    if i == 1:
        return (d_in - i) * (n_us[0] - 1)
    return (d_in - i) * (n_us[i-1] - n_us[i-2])

def fifo_load(g, node):
    '''
    Calculates the "FIFO load" for a given node assuming g represents the
    upstream network, and the downstream network is equivalent to the inverse
    of the upstream network.

    The fifo load is a metric representing the relative maximum fifo value reached
    by a single chip assuming all chips trigger at the same time.

    :param g: directed graph representing upstream network

    :param node: node within ``g`` to calculate fifo load

    :returns: ``int`` of fifo load

    '''
    in_links = g.out_edges(node)
    n_inputs = len(in_links)
    n_outputs = 1
    n_upstream_nodes = sorted([len(nx.descendants(g, link[1]))+1 for link in in_links])
    return sum([L(i, n_inputs, n_upstream_nodes) for i in range(-1,n_inputs)])

def network_fifo_load_score(g):
    '''
    Creates the network fifo load score as min(fifo load) + mean(fifo load).
    Modifies the ``'load'`` attribute of each node in order to save on
    computation time. When modifying the network connection (thus the fifo load),
    the ``'load'`` attributes should be cleared (see methods ``XX_edge_and_delete_fifo_load``).

    :param g: directed graph representing upstream network

    :returns: ``float``

    '''
    fifo_loads = []
    n = 0
    sum = 0
    max = 0
    for node in g.nodes():
        if not 'load' in g.nodes[node]:
            g.nodes[node]['load'] = fifo_load(g, node)
        if g.nodes[node]['load'] > max:
            max = g.nodes[node]['load']
        n += 1
        sum += g.nodes[node]['load']
    return max + sum / n

def add_edge_and_delete_fifo_load(g, edge):
    '''
    Creates edge in network and deletes the ``'load'`` attr from all nodes upstream
    of connection.

    :param g: directed graph of upstream network

    :param edge: edge to add to network

    '''
    g.add_edge(*edge)
    nodes = [edge[0]]
    while nodes:
        for node in nodes:
            if 'load' in g.nodes[node]:
                del g.nodes[node]['load']
        nodes = list(set(edge[0] for edge in g.in_edges(nodes)))

def remove_edge_and_delete_fifo_load(g, edge):
    '''
    Removes edge from network and deletes the ``'load'`` attr from all nodes
    upstream of connection.

    :param g: directed graph of upstream network

    :param edge: edge to remove from network

    '''
    g.remove_edge(*edge)
    nodes = [edge[0]]
    while nodes:
        for node in nodes:
            if 'load' in g.nodes[node]:
                del g.nodes[node]['load']
        nodes = list(set(edge[0] for edge in g.in_edges(nodes)))

def random_prune(g):
    '''
    Simple pruning algorithm:

        1. Find all edges going into nodes with in degree > 1

        2. Randomly remove (as long as all nodes maintain in degree > 1)

    :param g: directed graph representing upstream network

    :returns: ``g``

    '''
    edges_to_prune = [edge for edge in g.in_edges() if g.in_degree(edge[1]) > 1]
    random.shuffle(edges_to_prune)
    for edge in edges_to_prune:
        if g.in_degree(edge[1]) > 1:
            g.remove_edge(*edge)
    return g

def check_peturbations(g, edges, size, n, peturbation_delta=1e-6, pruning_algorithm=random_prune, scoring_algorithm=network_fifo_load_score):
    '''
    Check to see if a perturbations of the graph linkage improves (minimizes) performance

    :param g: directed graph of upstream network

    :param edges: edges to potentially add back into network (edges that already exist in network are ignored)

    :param size: number of edges to add back into network

    :param n: number of random perturbations to apply

    :param peturbation_delta: fractional change required to continue iteration

    :param pruning_algorithm: dedicated pruning algorithm to use (should take a single upstream directed graph as an argument and return a upstream single directed graph)

    :param scoring_algorithm: algorithm used to determine performance, this is the function we are minimizing (should take a single upstream directed graph as an argument and return a number)

    :returns: best performing graph found during iterations

    '''
    return_g = g
    while True:
        print('trying {} peturbations of scale {}...'.format(n, size))
        base_performance = network_fifo_load_score(return_g) # performance of iteration graph
        current_performance = base_performance # best performance of peturbation graphs
        new_edges = [edge for edge in edges if edge not in return_g.edges()]

        for i in range(n):
            random.shuffle(new_edges)
            test_g = deepcopy(return_g)
            for edge in new_edges[:min(size,len(new_edges))]:
                add_edge_and_delete_fifo_load(test_g, edge)
            test_g = pruning_algorithm(test_g)
            test_performance = network_fifo_load_score(test_g)
            if test_performance < current_performance:
                print('improved performance to {}'.format(test_performance))
                return_g = test_g
                current_performance = test_performance
        performance_delta = abs(current_performance - base_performance)/base_performance
        if performance_delta < peturbation_delta:
            break
        base_performance = current_performance
    return return_g

def generate_hydra_min_fifo_load_beam_search_digraphs(x_slots, y_slots, root, ext, avoid=None, seed=12345, peturbation_delta=1e-6, beam_width=3):
    '''
    Generates a simple hydra io networks through the following algorithm:

        1. create network with all connections between neighbors

        2. starting from root node, remove all incoming connections that have an outgoing connection

        3. iteratively prune remaing connections following:

            1. calculate a weight for each redundant connection based on the fifo load score of the network with and without the connection

            2. generate a list of potential graphs (with N-1 edges) that minimize the fifo load score

            3. keep ``beam_width`` of the best performing potential graphs for next iteration

            4. iterate until all graphs have no more redundant connections (choosing the most performant)

        4. perturb the solution N/4 times by

            1. randomly add 25% of the connections pruned in step (3.)

            2. reprune

            3. keep most performant

        5. continue to perturb until the fractional improvement drops below ``peturbation_delta``

    There is not a unique solution and so a random seed is used to generate the
    network.

    :param x_slots: maximum number of x positions for nodes

    :param y_slots: maximum number of y positions for nodes

    :param root: ``(x,y)`` position for root node, ``0 <= x < x_slots``, ``0 <= y < y_slots``

    :param ext: position of the node representing the external system

    :param avoid: ``list`` of ``(x,y)`` nodes to exclude from network

    :param seed: random seed for configuration (insures repeatabilty)

    :param peturbation_delta: continue to try peturbations if network score continues to change by this much (fractional, if None, don't check peturbations)

    :returns: 3 networkx ``DiGraph``s indicating the upstream miso network, the downstream miso network, and the mosi network

    '''
    random.seed(seed)

    g = generate_2d_grid_digraph(x_slots, y_slots, root, ext)
    #    g = nx.grid_2d_graph(x_slots, y_slots, create_using=nx.DiGraph) # base graph for upstream

    if avoid:
        g.remove_nodes_from(avoid)

    # create root
    g.remove_edges_from(list(g.in_edges(root)))

    # remove in edges from each successor
    nodes = list(g.successors(root))
    while nodes:
        random.shuffle(nodes)
        edges_to_remove = [edge for edge in g.in_edges(nodes) \
            if edge[::-1] in g.out_edges(nodes) \
            and g.in_degree(edge[1]) > 1]
        g.remove_edges_from(edges_to_remove)
        nodes = list(set([edge[1] for edge in g.out_edges(nodes)]))
    shortest_paths = deepcopy(list(g.edges()))

    def prune_networks(stack, beam_width=beam_width):
        '''
        Prunes redundant incoming network connections of an upstream directed
        graph using a beam search-like algorithm.

        :param stack: a directed graph or a list of directed graphs representing the upstream network

        :param beam_width: length of stack used during search

        :returns: directed graph with redundant incoming network connections pruned

        '''
        if not isinstance(stack, list):
            stack = [stack]
        stack.sort(key=lambda x: network_fifo_load_score(x))
        while len(stack) > beam_width:
            del stack[-1]
        completed_flag = True
        next_stack = []
        for g in stack:
            edges = [edge for edge in g.in_edges() if g.in_degree(edge[1]) > 1]
            if not edges:
                next_stack += [g]
            else:
                for idx,edge in enumerate(edges):
                    remove_edge_and_delete_fifo_load(g, edge)
                    score = network_fifo_load_score(g)
                    add_edge_and_delete_fifo_load(g, edge)
                    g.edges[edge]['weight'] = score
                min_weight = min([g.edges[edge]['weight'] for edge in edges])
                edges_to_prune = [edge for edge in edges if g.edges[edge]['weight'] == min_weight]
                if not edges_to_prune:
                    next_stack += [g]
                elif len(edges_to_prune) == 1:
                    remove_edge_and_delete_fifo_load(g, edges_to_prune[0])
                    completed_flag = False
                    next_stack += [g]
                else:
                    random.shuffle(edges_to_prune)
                    for edge in edges_to_prune:
                        next_stack += [deepcopy(g)]
                        remove_edge_and_delete_fifo_load(next_stack[-1], edge)
                        completed_flag = False
        if completed_flag:
            next_stack.sort(key=lambda x: network_fifo_load_score(x))
            return next_stack[0]
        return prune_networks(next_stack, beam_width=beam_width)

    g = prune_networks(g)

    if not peturbation_delta is None:
        size = int(max(len(shortest_paths)/4,1))
        n = int(max(len(shortest_paths)/4,1))
        g = check_peturbations(g, shortest_paths, size, n, peturbation_delta=peturbation_delta, pruning_algorithm=prune_networks, scoring_algorithm=network_fifo_load_score)

    return generate_digraphs_from_upstream(g, root, ext)

# Handle for the default configuration (use beam search and peturbations)
generate_hydra_min_fifo_load_digraphs = generate_hydra_min_fifo_load_beam_search_digraphs

def generate_hydra_min_fifo_load_base_digraphs(x_slots, y_slots, root, ext, avoid=None, seed=12345, peturbation_delta=None, beam_width=1):
    '''
    Handle for the ``generate_hydra_min_fifo_load_beam_search_digraphs``
    algorithm with diffent default arguments.

    '''
    return generate_hydra_min_fifo_load_beam_search_digraphs(x_slots, y_slots, root, ext, avoid=avoid, seed=seed, peturbation_delta=peturbation_delta, beam_width=beam_width)

def greedy_tree(g, root):
    '''
    Simple tree creation network for a grid-like set of nodes:

        1. Starting a root node, make all connections possible to neighbors

        2. Iterate on children created

    Insures shortest path to each node and meets simple hydra network requirements

    :param g: directed graph to add upstream connections

    :param root: root node used to start algorithm

    :returns: ``g``

    '''
    nodes = [root]
    while nodes:
        potential_links = []
        for node in nodes:
            children = [child for child in g.nodes() \
            if ((abs(node[0]-child[0]) == 1 and abs(node[1]-child[1]) == 0) \
            or (abs(node[0]-child[0]) == 0 and abs(node[1]-child[1]) == 1)) \
            and not (child == root or child == root)]
            potential_links += [(node,child) for child in children]
        random.shuffle(potential_links)
        for link in potential_links:
            if not nx.has_path(g,root,link[1]):
                g.add_edge(*link)
        nodes = list(set([edge[1] for edge in g.out_edges(nodes)]))
    return g

def generate_hydra_fifo_product_digraphs(x_slots, y_slots, root, ext, avoid=None, seed=12345, peturbation_delta=1e-6):
    '''
    Generates a simple hydra io networks through the following algorithm:

        1. create network with all connections between neighbors

        2. starting from root node, remove all incoming connections that have an outgoing connection

        3. create maximally spanning arborescence using fifo_load(head) * fifo_load(tail) as the weight

        4. perturb the solution N times by

            1. randomly adding 25% of the connections pruned in step (3.)

            2. reprune

            3. keep most performant

        5. continue to perturb until the fractional improvement drops below ``peturbation_delta``

    There is not a unique solution and so a random seed is used to generate the
    network.

    :param x_slots: maximum number of x positions for nodes

    :param y_slots: maximum number of y positions for nodes

    :param root: ``(x,y)`` position for root node, ``0 <= x < x_slots``, ``0 <= y < y_slots``

    :param ext: position of the node representing the external system

    :param avoid: ``list`` of ``(x,y)`` nodes to exclude from network

    :param seed: random seed for configuration (insures repeatabilty)

    :param peturbation_delta: continue to try peturbations if network score continues to change by this much (fractional, if None, don't check peturbations)

    :returns: 3 networkx ``DiGraph``s indicating the upstream miso network, the downstream miso network, and the mosi network

    '''

    random.seed(seed)

    g = generate_2d_grid_digraph(x_slots, y_slots, root, ext)
    #    g = nx.grid_2d_graph(x_slots, y_slots, create_using=nx.DiGraph) # base graph for upstream

    if avoid:
        g.remove_nodes_from(avoid)

    # create root
    g.remove_edges_from(list(g.in_edges(root)))

    # remove in edges from each successor
    nodes = list(g.successors(root))
    while nodes:
        random.shuffle(nodes)
        edges_to_remove = [edge for edge in g.in_edges(nodes) \
            if edge[::-1] in g.out_edges(nodes) \
            and g.in_degree(edge[1]) > 1]
        g.remove_edges_from(edges_to_remove)
        nodes = list(set([edge[1] for edge in g.out_edges(nodes)]))
    shortest_paths = deepcopy(list(g.edges()))

    # calculate fifo product
    network_fifo_load_score(g)
    for edge in g.edges():
        g.edges[edge]['weight'] = g.nodes[edge[0]]['load'] * g.nodes[edge[1]]['load']

    g = nx.maximum_spanning_arborescence(g)

    if not peturbation_delta is None:
        size = int(max(len(shortest_paths)/4,1))
        n = len(shortest_paths)
        g = check_peturbations(g, shortest_paths, size, n, peturbation_delta=peturbation_delta, pruning_algorithm=random_prune, scoring_algorithm=network_fifo_load_score)

    return generate_digraphs_from_upstream(g, root, ext)


def generate_hydra_greedy_tree_digraphs(x_slots, y_slots, root, ext, avoid=None, seed=12345):
    '''
    Generates simple hydra io networks via the simple algorithm:

        1. starting a root node, make all outgoing connections to neighbors

        2. iterating on resulting children, make all outgoing connections to neighbors (as long as the in degree of the neighbor is < 1)

    :param x_slots: maximum number of x positions for nodes

    :param y_slots: maximum number of y positions for nodes

    :param root: ``(x,y)`` position for root node, ``0 <= x < x_slots``, ``0 <= y < y_slots``

    :param ext: position of the node representing the external system

    :param avoid: ``list`` of ``(x,y)`` nodes to exclude from network

    :param seed: random seed for configuration (insures repeatabilty)

    :returns: 3 networkx ``DiGraph``s indicating the upstream miso network, the downstream miso network, and the mosi network

    '''
    random.seed(seed)

    g = nx.DiGraph()
    for x in range(x_slots):
        for y in range(y_slots):
            g.add_node((x,y))
    g.add_node(ext)
    g.add_node(root)

    if avoid:
        g.remove_nodes_from(avoid)

    g = greedy_tree(g, root)

    return generate_digraphs_from_upstream(g, root, ext)


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
        '_config_type': 'controller',
        'name': '{}'.format(max(g.nodes())),
        'asic_version': 2,
        'layout': None,
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
    network_config['network'][io_group][io_channel]['nodes'] = []

    if not 'miso_uart_map' in network_config['network']:
        network_config['network']['miso_uart_map'] = default_miso_uart_map
    if not 'mosi_uart_map' in network_config['network']:
        network_config['network']['mosi_uart_map'] = default_mosi_uart_map
    if not 'usds_link_map' in network_config['network']:
        network_config['network']['usds_link_map'] = default_usds_link_map

    subnetwork = network_config['network'][io_group][io_channel]
    if not default_miso_uart_map == network_config['network']['miso_uart_map']:
        subnetwork['miso_uart_map'] = default_miso_uart_map
    if not default_mosi_uart_map == network_config['network']['mosi_uart_map']:
        subnetwork['mosi_uart_map'] = default_mosi_uart_map
    if not default_usds_link_map == network_config['network']['usds_link_map']:
        subnetwork['usds_link_map'] = default_usds_link_map

    next_nodes = [node for node in g.nodes() if 'root' in g.nodes[node]]
    while next_nodes:
        for node in next_nodes:
            subnetwork['nodes'] += [{
                'chip_id': g.nodes[node]['chip_id'],
                'miso_us': [None]*4
                }]
            chip_config = subnetwork['nodes'][-1]
            for child in g.successors(node):
                child_idx = dir_table[edge_dir((node,child))]
                chip_config['miso_us'][child_idx] = g.nodes[child]['chip_id']
            if not any(chip_config['miso_us']):
                del chip_config['miso_us']
            if 'root' in g.nodes[node]:
                chip_config['root'] = True
        next_nodes = [edge[1] for edge in g.out_edges(next_nodes)]
    return network_config

def plot(g, name='default', labels='chip_id', figsize=(6, 6), interactive=True):
    '''
    Draws a network configuration graph (using matplotlib)

    :param g: A networkx graph object representing the configuration, each node must be a 2-``tuple`` with a ``'chip_id'`` field

    :param name: Figure name (if `'default'` will clear plot before redrawing)

    :param labels: Attribute to label nodes by, if None, don't label nodes

    :param figsize: Size of figure to draw

    :param interactive: turn on pyplot's interactive mode

    '''
    import matplotlib.pyplot as plt
    if interactive:
        plt.ion()
    plt.figure(name, figsize=figsize)
    if name == 'figure':
        plt.cla()
    if labels:
        nx.draw_networkx(g, dict([(node,node) for node in g.nodes]), labels=dict([(node,g.nodes[node][labels]) for node in g.nodes]))
    else:
        nx.draw_networkx(g, dict([(node,node) for node in g.nodes]), labels=dict([(node,'') for node in g.nodes]))
    plt.xlabel('x index')
    plt.ylabel('y index')
    plt.tight_layout()
    if not interactive:
        plt.savefig(name+'.png')

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
    parser.add_argument('--root', '-r', type=json.loads, required=False, default=None, help='''
        position for root node as list '[x,y]', (optional, default=<ext node>)
        ''')
    parser.add_argument('--ext', '-e', type=json.loads, required=True, help='''
        position for ext node as list '[x,y]', (optional, default=<ext node>)
        ''')
    parser.add_argument('--avoid', type=json.loads, required=False, default=list(), help='''
        positions of nodes to avoid, specified as list of x, y positions '[[x,y],[x,y]]'
        ''')
    parser.add_argument('--chip_id', type=str, required=False, default='chip_id_simple',
        help='''sets method for generating and assigning chip ids, options are
        'chip_id_simple' and 'chip_id_position'
        ''')
    parser.add_argument('--algorithm', type=str, required=False, default='simple2',
        help='''sets method for generating network links, options are 'min_fifo_load', 'min_fifo_load_base', 'min_fifo_load_beam_search', 'fifo_product', 'greedy_tree', 'simple', and 'simple2
        ''')
    parser.add_argument('--io_group', type=int, required=False, default=1,
        help='''sets io group
        ''')
    parser.add_argument('--io_channel', type=int, required=False, default=1,
        help='''sets io channel
        ''')
    parser.add_argument('--plot', action='store_true', help='''
        flag to plot network instead of generating file
        ''')

    args = parser.parse_args()
    outfile = args.outfile
    if not outfile:
        outfile = args.name + '.json'
    avoid = [tuple(pos) for pos in args.avoid]
    ext = tuple(args.ext)
    root = tuple(args.root) if args.root is not None else ext
    print('seed is {}'.format(args.seed))
    print('creating {}x{} network with {} starting at {}, avoiding {}...'.format(args.x_slots, args.y_slots, args.algorithm, root, avoid))
    g_us, g_ds, g_mosi = globals()['generate_hydra_' + args.algorithm + '_digraphs'](args.x_slots,
        args.y_slots, root, ext, avoid=avoid, seed=args.seed)

    print('generating chip ids...')
    generate_chip_id(g_us, method=args.chip_id) # add chip ids to each node
    generate_chip_id(g_ds, method=args.chip_id) # add chip ids to each node
    generate_chip_id(g_mosi, method=args.chip_id) # add chip ids to each node

    print('calculating metrics...')
    fifo_loads = [fifo_load(g_us, node) for node in g_us.nodes()]
    n_children = [len(nx.descendants(g_us,node)) for node in g_us.nodes()]
    print('nodes: ', len(fifo_loads))
    print('mean fifo load: ', np.mean(fifo_loads))
    print('max fifo load: ', max(fifo_loads))

    if args.plot:
        plot(g_us, name='MISO upstream')
        plot(g_ds, name='MISO downstream')
        plot(g_mosi, name='MOSI')
        print('Press enter to quit')
        input()
        exit()

    else:
        plot(g_us, name=outfile[:-5], interactive=False)

        previous_config = None
        if os.path.exists(outfile):
            print('loading existing file',outfile)
            with open(outfile,'r') as f:
                previous_config = json.load(f)
        new_config = generate_network_config((g_us, g_ds, g_mosi), args.io_group, args.io_channel, name=args.name, previous=previous_config)
        with open(outfile,'w') as f:
            json.dump(new_config, f, indent=4)
