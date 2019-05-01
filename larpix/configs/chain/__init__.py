'''
This module contains daisy chain configuration files.
The format is a standard JSON file structured as follows:

.. parsed-literal::
    {
        "name": <string identifier for daisy chain (typically pcb-<int>)>,
        "chip_list": [<A list of [chip, daisy-chain id>] pairs, one for each chip>]
    }

The order in which chips are declared in the ``'chip_list'`` sets the order within the ``Controller`` daisy chain.
All fields are necessary.
'''
pass
