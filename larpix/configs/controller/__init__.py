'''
This module contains controller configuration files, used to specify the physical
asics present and their network structure

V2 Configuration
----------------

The v2 configuration file is a standard JSON file structured as follows:

.. parsed-literal::
    {
        "_config_type": "controller",
        "_include": [<optional list of files to inherit from>],
        "name": <string identifier for configuration ID, e.g. "pcb-3", or "acube-2x2">,
        "layout": <string identifier for layout version, e.g. "1.2.0">,
        "asic_version": 2,
        "network": {
            "miso_uart_map": [<uart channel for position in array, required>, ...],
            "mosi_uart_map": [<uart channel for position in array, required>, ...],
            "usds_link_map": [<position of chip relative to neighbor, required>, ...],
            "<io_group>": {
                "miso_uart_map": [<uart channels for io_group, optional>, ...],
                ...
                "<io_channel>": {
                    "miso_uart_map": [<uart channels for io_group, optional>, ...],
                    ...
                    "nodes": [
                        {
                            "chip_id": <chip id of first chip to load into network>,
                            "miso_us": [<chip_ids of upstream chips, null if no upstream chip, optional>],
                            "miso_ds": [<chip_ids of downstream chips, optional>],
                            "mosi": [<chip_ids of chips to listen to, optional>],
                            "root": <bool indicating if this is a root node, optional>,
                            "miso_uart_map": [<uart channels for chip, optional>, ...],
                            ...
                        },
                        ...
                    ]
                },
                ...
            },
            ...
        }
    }

The structure allows for a lot of flexibility in the network configuration, while
maintaining a relatively terse format for simple configurations. Generally, a
Hydra network can be described using three directed graphs which we call
miso upstream (``miso_us``), miso downstream (``miso_ds``), and mosi (``mosi``). The ``miso_us`` graph
represents the flow of outgoing upstream packets (i.e. the direction of configuration
write packets). The ``miso_ds`` graph represents the flow of outgoing downstream packet
(i.e. the direction of configuration read and data packets). The ``mosi`` graph
represents the flow of incoming packets of either type. The overall LArPix
network is then defined with a collection of Hydra networks, each associated
with a specific io_group and io_channel. The ``io_group``, ``io_channel`` pair must
be unique for each Hydra network.

For the configuration file, the basic requirement for each hydra network is that for each
node in the network, you must specify a chip id. The chip id must be an integer
between 2 and 254 for an ASIC, but other systems (i.e. an FPGA that can interpret
the LArPix UART protocol) can be specified by a string. Each chip id must be
unique within each io_group, io_channel sub-network.

To specify links within the 3 directed graphs (``miso_us``, ``miso_ds``, and ``mosi``), a
4-item array is used. Each 4-item array indicates the chip id of the neighboring
nodes that should be connected to the given chip. So for example::

    {
        "chip_id": 23,
        "miso_us": [24,null,null,null],
        "miso_ds": [null,22,null,null],
        "mosi":    [24,22,null,null]
    }

will create a ``miso_us`` graph where data flows from chip 23 to chip 24, a ``miso_ds``
graph where data flows from chip 23 to chip 22, and a ``mosi`` graph where data
flows from chip 24 to 23 and chip 22 to 23 (note the opposite convention for the
mosi graph).

The position of the chip id within the 4-item array indicates the relative physical
location of the neighboring chip. A suggested ordering might be
``[<top>,<left>,<down>,<right>]``, thus the previous example indicates
that the current chip should be linked to chip 24 which is above the current chip.
The definition of ``<top>``, ``<left>``, ``<down>``, and ``<right>`` is fixed by which of
the four LArPix UARTs is used to communicate to a chip in that position. This
is declared with the ``"miso_uart_map"`` and ``"mosi_uart_map"`` definitions.
As an example, the upper left corner of the LArPix ASIC is UART 0 and the upper
right corner of the chip is UART 3, thus we can define
``<top>`` as the first position in each array by declaring
``"miso_uart_map": [3,X,X,X]`` and ``"mosi_uart_map": [0,X,X,X]`` which will read
packets in on UART 0 and send packets out on UART 3. It doesn't matter where
in the array ``<top>`` is defined, as long as you have a consistent convention between
the ``miso_uart_map``, ``mosi_uart_map``, and each of your network node's (``miso_us``, ``miso_ds``,
and ``mosi``).

It would become very tedious and difficult to debug if for every node you had
to specify all of the links on all three of the graphs, so the configuration
parser is smarter than that. Most of the time, the networks that you'll want to
specify have the same upstream and downstream connections (albeit with the
directions flipped), so if the ``"miso_ds"`` field is not explicitly defined, it
will be inferred based on the ``miso_us`` network that was created. Likewise, usually
the ``mosi`` connections should be the same as the upstream and downstream connections.
Thus, if this field is not set explicitly it will be inferred automatically based
on the ``miso_us`` graph and the ``miso_ds`` graph.

However, in order for the auto-parsing methods to work, they need some information
about how the chips are oriented with respect to each other. This is defined by
the ``"usds_link_map"``. This field is also a 4-item array, however the value now
represents the position of the given chip from the perspective of the neighbor.

So, following the example from above, we can define two directions ``<top>`` and
``<bottom>`` with ``"miso_uart_map": [3,X,1,X]`` and ``"mosi_uart_map": [0,X,2,X]``.
If we have two chips (let's say 22 and 23 with chip 23 above chip 22), to
determine the ``"usds_link_map"`` we have to consider both where chip 23 is from the
perspective of chip 22 (``<top>``, or index 0 from our definition) and where chip 22
is from the perspective of chip 23 (``<bottom>``, or index 2 from out definition).
This means that the ``"usds_link_map"`` for chip 22 should be ``[2,X,X,X]``, or in
other words, the chip (23) that is in the direction of ``<top>`` (index 0) from
the current chip (22) sees the current chip (22) in the direction of ``<down>``
(index 2). Likewise the ``"usds_link_map"`` for chip 23 should be ``[X,X,0,X]``.
Now as long as you maintain the same definitions of ``<top>`` and ``<bottom>`` for
all of the chips in the network, you can set ``"usds_link_map"`` at the top level
to be ``[2,X,0,X]`` you don't need to worry about figuring this out for each
node in the network... phew.

The final necessary component of the configuration is to declare some nodes
as ``root`` nodes. These are special nodes which are used to indicate the first
node to be configured during the initialization of the network. Typically, the
placeholder node representing the external system is set as the root node.


Putting all of this together, a simple example of a complete network
configuration is provided below:

.. parsed-literal::
    "network": {
        "1": {
            "2": {
                "nodes": [
                    {
                        "chip_id": "ext",
                        "miso_us": [null,null,2,null],
                        "root": true
                    }
                    {
                        "chip_id": 2,
                        "miso_us": [null,3,null,null]
                    },
                    {
                        "chip_id": 3
                    }
                ]
            }
        }
        "miso_uart_map": [3,0,1,2],
        "mosi_uart_map": [0,1,2,3],
        "usds_link_map": [2,3,0,1]
    }

In this example, we define a single 2-chip Hydra network with ``io_group=1``
and ``io_channel=2``. The ``"nodes"`` array is filled with ``dict``s representing each
node in the network. Globally, we've defined our "directions" with the
``miso_uart_map`` and ``mosi_uart_map``, and we've set up the ``usds_link_map`` so
that the auto-parsing algorithm can work. Within the ``"nodes"`` array, we specify
three nodes (``ext``, ``2``, ``3``); two of which represent chips (``2``, ``3``), and one of
which represents the external FPGA used to communicate with the network (``ext``).
The external FPGA is set as the ``root`` node so that the initialization of the
network starts from there. We've declared ``miso_us`` links for the ``ext`` and
``2`` nodes, but because we have not specified any ``miso_ds`` or ``mosi`` links, the
auto-parsing algorithm with generate the following graphs::

    miso_us: 'ext'  -> 2  -> 3
    miso_ds: 'ext' <-  2 <-  3
    mosi:    'ext' <-> 2 <-> 3

with the active uarts::

    miso_us: 1    -> 0    -> X
    miso_ds: X   <-  3   <-  2
    mosi:    2,0 <-> 1,3 <-> 3

Or, assuming you are using our definition above for ``<top>``, ``<bottom>``, etc.::

       ext
        v
    3 < 2

The top-level ``"_include"`` field can be used to specify files to inherit from.
All fields of the configuration down to the ``"nodes"`` array level can be inherited.
A standard use for this would be to specify each hydra network for a given channel
independently, and inherit from all of the files in a single configuration
file. E.g.::

    {
        "_config_type": "controller",
        "_include": [
            "network-1-1.json",
            "network-1-2.json",
            "network-1-3.json",
            "network-1-4.json",
            "network-2-1.json",
            "network-2-2.json",
            "network-2-3.json",
            "network-2-4.json"
            ],
        "name": "multi-io-group-network"
    }


LightPix Configuration
----------------------

LightPix uses the same interface as LArPix v2 but with::

    "asic_version": "lightpix-v1.0"


V1 Configuration
----------------

The v1 configuration file is a standard JSON file structured as follows:

.. parsed-literal::
    {
        "name": <string identifier for PCB ID, e.g. "pcb-3">,
        "layout": <string identifier for layout version, e.g. "1.2.0">,
        "asic_version": 1,
        "chip_list": [<A list of chip keys, one for each chip, in daisy-chain order>]
    }

All fields are necessary.

See the larpix-geometry documentation
<https://github.com/samkohn/larpix-geometry> for a listing of all the
layout versions.
'''
pass
