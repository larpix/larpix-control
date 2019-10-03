'''
This module contains controller configuration files, used to specify the physical
asics present and their network structure

The v2 configuration file is a standard JSON file structured as follows:

.. parsed-literal::
    {
        "name": <string identifier for configuration ID, e.g. "pcb-3", or "acube-2x2">,
        "layout": <string identifier for layout version, e.g. "1.2.0">,
        "type": "network",
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
                    "chips": [
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
maintaining a relatively terse format for simple configurations. The basic logic
is that for each chip, you must specify a chip id. If you'd like to add chips
to the miso_us network for a chip, you can specify their chip ids in a list
of 4 upstream channels. Values of null are ignored, and non-integer values are
interpreted as placeholders (i.e. no physical chip, but we'd like to enable the
miso_us channel for some reason or another). The channel of the uart to enable/disable
during the configuration of the network is gleaned from the "miso_us_uart_map".
The "miso_us_uart_map" can be specified at any layer of the configuration (io
group, io channel, or chip) and will override the values specified at the
network level.

A similar logic applies for the miso_ds network, however by default, this network
uses the converse of the miso_us configuration (with the uart channel specified
by "miso_ds_uart_map"). For example, to declare a miso_us/miso_ds connection
between two chips, you may simple declare:

    "chips": [
        {"chip_id": 2, "miso_us":[3,null,null,null], "miso_us_uart_map": [0,1,2,3]},
        {"chip_id": 3, "miso_ds_uart_map": [2,3,0,1]}
    ]

This will initialize chip 2 with the miso_us enabled on uart channel 0 and
chip 3 with the miso_ds enabled on uart channel 2. Placeholders can (and should)
be used with miso_ds as well. It is recommended to use the ``'ext'`` node to
indicate the connnection to the external system (warm electronics or the like).

For the mosi network, the default behavior is to use the converse of both the
miso_us and miso_ds network using the same uarts. E.g. the above example would
have chip 2 with mosi enabled on uart channel 0 and chip 3 with mosi enabled on
uart channel 2. You can override this behavior by using ``"mosi": [<chip_ids to link>]``.

Finally, the ``'root'`` field is used to specify special 'root' nodes within the
network. These are the nodes that will be configured first when initializing a
network (with the next nodes order of configuration determined via the mosi_us
configuration). If not specified, the node is assumed to not be a root node.



The v1 configuration file is a standard JSON file structured as follows:

.. parsed-literal::
    {
        "name": <string identifier for PCB ID, e.g. "pcb-3">,
        "layout": <string identifier for layout version, e.g. "1.2.0">,
        "type": "controller",
        "chip_list": [<A list of chip keys, one for each chip, in daisy-chain order>]
    }

All fields are necessary.

See the larpix-geometry documentation
<https://github.com/samkohn/larpix-geometry> for a listing of all the
layout versions.
'''
pass
