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
            "miso_us_uart_map": [<uart channel for position in array, required>, ...],
            "miso_ds_uart_map": [<uart channel for position in array, required>, ...],
            "mosi_uart_map": [<uart channel for position in array, required>, ...],
            "<io_group>": {
                "miso_us_uart_map": [<uart channels for io_group, optional>, ...],
                ...
                "<io_channel>": {
                    "miso_us_uart_map": [<uart channels for io_group, optional>, ...],
                    ...
                    "nodes": [
                        {
                            "chip_id": <chip id of first chip to load into network>,
                            "miso_us": [<chip_ids of upstream chips, null if no upstream chip, optional>],
                            "miso_ds": [<chip_ids of downstream chips, optional>],
                            "mosi": [<chip_ids of chips to listen to, optional>],
                            "root": <bool indicating if this is a root node, optional>,
                            "miso_us_uart_map": [<uart channels for chip, optional>, ...],
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
miso upstream (miso_us), miso downstream (miso_ds), and mosi. The miso_us graph
represents the flow of outgoing upstream packets (i.e. the direction of configuration
write packets). The miso_ds graph represents the flow of outgoing downstream packet
(i.e. the direction of configuration read and data packets). The mosi graph
represents the flow of incoming packets of either type. The overall LArPix
network is then defined with a collection of Hydra networks, each associated
with a specific io_group and io_channel. The io_group, io_channel pair must
be unique for each Hydra network.

For the configuration file, the basic logic for each hydra network is that for each
chip, you must specify a chip id. Links within the directed graphs are then specified via
4-item arrays. A simplified example is provided below:

.. parsed-literal::
    "network": {
        "1": {
            "2": {
                "chips": [
                    {
                        "chip_id": "ext",
                        "miso_us": [null,null,2,null]
                    }
                    {
                        "chip_id": 2,
                        "miso_us": [3,null,null,null],
                        "root": true
                    },
                    {
                        "chip_id": 3
                    }
                ]
            }
        }
        "miso_us_uart_map": [0,1,2,3],
        "miso_ds_uart_map": [2,3,0,1],
        "mosi_uart_map": [0,1,2,3]
    }

In this example, we define a single 2-chip Hydra network with io_group=1
and io_channel=2. The "chips" array is filled with dicts representing each
chip in the network. Within the chip specification, the "chip_id" field sets
the chip_id configuration register for that chip and must be unique within
each io_group, io_channel sub-network. The "miso_us" array lists the chip_ids
that should receive upstream packets from this chip's miso_us channels. Using
the miso_us_uart map specified in the example, index=0 refers to a connection on
miso uart channel 0, index=1 refers to uart channel 1, etc. The miso_us should
be specified for each chip that is linked to other chips.

'Dummy' nodes can be specified by using a string for the "chip_id", rather than
an integer. These represent network links to non-chip object, e.g. an fpga, etc.
In general, you must specify one dummy link that points to at least one chip on
the "miso_us" network.

In each network there must be at least 1 "root" node. The node must have the
"root" field set to true. This determines the order in which chips will be configured.
The uart channel of each position in miso_ds network is inferred by the
miso_ds_uart_map, so for the example configuration uart0 of chip 2 will send
downstream packets. All other network links will be inferred from these fields.

If you'd like to manually specify miso_us links for a chip,
you can specify their chip ids in a list of 4 upstream channels. Values of null
are ignored, and non-integer values are interpreted as placeholders (i.e. no
physical chip, but we'd like to enable the miso_us channel for some reason or
another). The physical uart to enable/disable
during the configuration of the network is gleaned from the "miso_us_uart_map".
The "miso_us_uart_map" can be specified at any layer of the configuration (io
group, io channel, or chip) and will override the values specified at the
network level.

A similar logic applies for the miso_ds, however by default, this network
uses the converse of the miso_us configuration (with the uart channel specified
by "miso_ds_uart_map"). For example, to declare a miso_us/miso_ds connection
between two chips, you may simple declare:

    "chips": [
        {
            "chip_id": 2,
            "miso_us":[3,null,null,null],
            "miso_us_uart_map": [0,1,2,3]
        },
        {
            "chip_id": 3,
            "miso_ds_uart_map": [2,3,0,1]
        }
    ]

This will initialize chip 2 with the miso_us enabled on uart channel 0 and
chip 3 with the miso_ds enabled on uart channel 2. Placeholders (such as 'ext')
be used with miso_ds as well.

For mosi, the default behavior is to use the converse of both the
miso_us and miso_ds graphs using the same uarts. E.g. the above example would
have chip 2 with mosi enabled on uart channel 0 and chip 3 with mosi enabled on
uart channel 2. You can override this behavior by setting the "mosi" field to
an array of the chips to link on the mosi graph. To override which physical uart
to used, the "mosi_uart_map" is used in a similar fashion as miso_us.

To properly create the uart maps, it requires knowing the routing of mosi/miso
channels between the chips. The miso_us_uart_map determines which uart miso
channel to enable if a miso upstream graph edge originates from the given chip.
The miso_ds_uart_map determines which uart miso channel to enable if an a miso
downstream graph edge originates from the given chip. And the mosi_uart_map
determines which uart channel to enable if a mosi graph edge ends on the given
chip. E.g.::

    "miso_us_uart_map": [3,0,1,2],
    "miso_ds_uart_map": [1,2,3,0],
    "mosi_uart_map": [0,3,2,1]

declares that a link created at index 1 will use uart channel 0 (if it is a miso_us link),
channel 2 (if it is a miso_ds link), or channel 3 (if it is a mosi link).

Finally, the ``'root'`` field is used to specify special 'root' nodes within the
network. These are the nodes that will be configured first when initializing a
network (with the next nodes order of configuration determined via the mosi_us
configuration). If not specified, the node is assumed to not be a root node.

The top-level "_include" field can be used to specify files to inherit from.
All fields of the configuration down to the "chips" array level can be inherited.
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
        "layout": null
    }


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
