'''
This module contains daisy chain configuration files.
The format is a standard JSON file structured as follows:

.. parsed-literal::
    {
        "name": <string identifier for PCB ID, e.g. "pcb-3">,
        "layout": <string identifier for layout version, e.g. "1.2.0">,
        "chip_list": [<A list of chip keys, one for each chip, in daisy-chain order>]
    }

All fields are necessary.

See the larpix-geometry documentation
<https://github.com/samkohn/larpix-geometry> for a listing of all the
layout versions.
'''
pass
