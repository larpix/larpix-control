'''
This module contains io configuration files used by io classes to look up
detector components based on the ``io_group`` and ``io_channel`` contained within
chip keys. See the larpix core documentation for more details on ``larpix.Key``
objects.

JSON formatting
---------------

The format is a standard JSON file structured as follows:

.. parsed-literal::
    {
        "_config_type": "io",
        "io_class": "<name of io class config should be used with>",
        "io_group": [
            [<io group number>, <assoc. value to be used by io class>],
            ...
        ]
    }

Field description
-----------------

The ``"_config_type": "io"`` field is used in loading for validation (so that
you don't accidentally try to load a ``chip`` config into your io class. This
will always be "io" for io confiugration files.

The ``"io_class": "<name>"`` field is used to specify the io class that the
configuration is compatible with. Examples are provided for each built-in io
class.

The ``"io_group": [[<group #>, <io class spec.>], ...]`` list is a list of pairs
used to create a map between the ``io_group`` number and the internal
representation used by the io class. E.g. the MultiZMQ_IO uses the IP address to
identify the ``io_group``.

'''
pass
