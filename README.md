# larpix-control

Control the LArPix chip

[![Documentation Status](https://readthedocs.org/projects/larpix-control/badge/?version=stable)](https://larpix-control.readthedocs.io/en/stable/?badge=stable)
[![Build Status](https://travis-ci.com/larpix/larpix-control.svg?branch=master)](https://travis-ci.com/larpix/larpix-control)

## Setup and installation

This code is intended to work on both Python 2.7+ and Python 3.6+.

Install larpix-control from pip with

```
pip install larpix-control
```

To return your namespace to the pre-larpix state, just
run `pip uninstall larpix-control`. If you'd prefer to download the code
yourself, you can. Just run `pip install .` from the root directory of
the repository.

### Tests

You can run tests to convince yourself that the software works as
expected. After `pip install`ing this package, you can run the tests
from the repository root directory with the simple command `pytest`.

You can read the tests to see examples of how to call all of the common
functions.

## File structure

The larpix package contains:
```
larpix
├── __init__.py
├── bitarrayhelper.py
├── chip.py
├── configs
│   ├── __init__.py
│   ├── chip
│   │   ├── __init__.py
│   │   ├── csa_bypass.json
│   │   ├── default.json
│   │   ├── default_v2.json
│   │   ├── physics.json
│   │   └── quiet.json
│   ├── controller
│   │   ├── __init__.py
│   │   ├── pcb-10_chip_info.json
│   │   ├── pcb-1_chip_info.json
│   │   ├── pcb-2_chip_info.json
│   │   ├── pcb-3_chip_info.json
│   │   ├── pcb-4_chip_info.json
│   │   ├── pcb-5_chip_info.json
│   │   ├── pcb-6_chip_info.json
│   │   └── v2_example.json
│   └── io
│       ├── __init__.py
│       ├── daq-srv1.json
│       ├── daq-srv2.json
│       ├── daq-srv3.json
│       ├── daq-srv4.json
│       ├── daq-srv5.json
│       ├── daq-srv6.json
│       ├── daq-srv7.json
│       ├── default.json
│       └── loopback.json
├── configuration
│   ├── __init__.py
│   ├── configuration.py
│   ├── configuration_v1.py
│   └── configuration_v2.py
├── controller.py
├── example.py
├── format
│   ├── __init__.py
│   ├── hdf5format.py
│   └── message_format.py
├── io
│   ├── __init__.py
│   ├── fakeio.py
│   ├── io.py
│   ├── multizmq_io.py
│   ├── serialport.py
│   └── zmq_io.py
├── key.py
├── larpix.py
├── logger
│   ├── __init__.py
│   ├── h5_logger.py
│   ├── logger.py
│   └── stdout_logger.py
├── packet
│   ├── __init__.py
│   ├── message_packet.py
│   ├── packet_collection.py
│   ├── packet_v1.py
│   ├── packet_v2.py
│   └── timestamp_packet.py
├── quickstart.py
├── serial_helpers
│   ├── __init__.py
│   ├── analyzers.py
│   ├── dataformatter.py
│   ├── dataloader.py
│   └── datalogger.py
└── timestamp.py
```

## Minimal working example

So you're not a tutorials kind of person. Here's a minimal working
example for you to play around with:

```python
>>> from larpix import Controller, Packet_v2
>>> from larpix.io import FakeIO
>>> from larpix.logger import StdoutLogger
>>> controller = Controller()
>>> controller.io = FakeIO()
>>> controller.logger = StdoutLogger(buffer_length=0)
>>> controller.logger.enable()
>>> chip1 = controller.add_chip('1-1-2', version=2)  # (access key)
>>> chip1.config.threshold_global = 25
>>> controller.write_configuration('1-1-2', chip1.config.register_map['threshold_global']) # chip key, register 64
[ Key: 1-1-2 | Chip: 2 | Upstream | Write | Register: 64 | Value: 25 | Parity: 1 (valid: True) ]
Record: [ Key: 1-1-2 | Chip: 2 | Upstream | Write | Register: 64 | Value: 25 | Parity: 1 (valid: True) ]
>>> packet = Packet_v2(b'\x02\x91\x15\xcd[\x07\x85\x00')
>>> packet_bytes = packet.bytes()
>>> pretend_input = ([packet], packet_bytes)
>>> controller.io.queue.append(pretend_input)
>>> controller.run(0.05, 'test run')
Record: [ Key: None | Chip: 2 | Downstream | Data | Channel: 5 | Timstamp: 123456789 | Dataword: 145 | Trigger: normal | Local FIFO ok | Shared FIFO ok | Parity: 0 (valid: True) ]
>>> print(controller.reads[0])
[ Key: None | Chip: 2 | Downstream | Data | Channel: 5 | Timstamp: 123456789 | Dataword: 145 | Trigger: normal | Local FIFO ok | Shared FIFO ok | Parity: 0 (valid: True) ]
```

## Tutorial

This tutorial runs through how to use all of the main functionality of
larpix-control.

To access the package contents, use one of the two following `import`
statements:

```python
import larpix  # use the larpix namespace
# or ...
from larpix import *  # import all core larpix classes into the current namespace
```

The rest of the tutorial will assume you've imported all of the core larpix
classes via a ``from larpix import *`` command.

### Create a LArPix Controller

The LArPix Controller translates high-level ideas like "read
configuration register 10" into communications to and from LArPix ASICs,
and interprets the received data into a usable format.

Controller objects communicate with LArPix ASICs via an IO interface.
Currently available IO interfaces are ``SerialPort``, ``ZMQ_IO`` and
``FakeIO``. We'll work with ``FakeIO`` in this tutorial, but all the
code will still work with properly initialized versions of the other IO
interfaces.

Set things up with

```python
from larpix.io import FakeIO
from larpix.logger import StdoutLogger
controller = Controller()
controller.io = FakeIO()
controller.logger = StdoutLogger(buffer_length=0)
controller.logger.enable()
```

The ``FakeIO`` object imitates a real IO interface for testing purposes.
It directs its output to stdout (i.e. it prints the output), and it
takes its input from a manually-updated queue. At the end of each
relevant section of the tutorial will be code for adding the expected
output to the queue. You'll have to refill the queue each time you run
the code.

Similarly, the ``StdoutLogger`` mimics the real logger interface for testing. It
prints nicely formatted records of read / write commands to stdout every
``buffer_length`` packets. The logger interface requires enabling the
logger before messages will be stored. Before ending the python session, every
logger should be disabled to flush any remaining packets stored in the buffer.

### Set up LArPix Chips

Chip objects represent actual LArPix ASICs. For each ASIC you want to
communicate with, create a LArPix Chip object and add it to the
Controller.

```python
chipid = 5
chip_key = '1-1-5'
chip5 = controller.add_chip(chip_key, version=2)

chip5 = controller[chip_key] # get chip object
chip5 = controller[1,1,5] # gets same chip object
```

The `chip_key` field specifies the necessary information for the `controller.io`
object to route packets to/from the chip. The details of how this key maps to a
physical chip is implemented separately for each `larpix.io` class.

The key itself consists of 3 1-byte integer values that represent the 3
low-level layers in larpix readout:

  - the io group: this is the highest layer and represents a control system that
  communicates with multiple IO channels

  - the io channel: this is the middle layer and represents a single MOSI/MISO
  pair

  - the chip id: this is the lowest layer and represents a single chip on a
  MOSI/MISO network

If you want to interact with chip keys directly, you can instantiate one using
a valid keystring (three 1-byte integers separated by dashes, e.g. ``'1-1-2'``).
Please note that the ids of 0, 1, and 255 are reserved for special functions.

```python
from larpix import Key
example_key = Key(1,2,3)
```

You can grab relevant information from the key via a number of useful methods
and attributes:

```python
example_key.io_group  # 1
example_key.io_channel  # 2
example_key.chip_id  # 3
example_key.to_dict() # returns a dict with the above keys / values
```

If you are using a ``Key`` in a script, we recommend that you generate the keys
via the ``Key(<io_group>,<io_channel>,<chip_id>)`` method which will protect against updates to the keystring
formatting.

You can read the docs to learn more about ``Key`` functionality.

### Set up LArPix Hydra network

With the the LArPix v2 asic, a network io structure is used. To keep track of
this network and to insure the proper bring-up procedure is followed. The
controller has a ``network`` attribute. This is an ordered dict with multiple
layers corresponding to the chip key layers. It assumes that each hydra network
is distinct on a given io channel. On a given io channel, the hydra network is
represented as three directed graphs ``miso_us``, ``miso_ds``, and ``mosi``.

```python
controller.network[1] # Represents all networks on io group 1
controller.network[1][1] # Represents the network on io group 1, io channel 1
controller.network[1][1]['mosi'] # directed graph representing mosi links
```

Nodes within the network are added automatically whenever you add a chip to the
controller:

```python
list(controller.network[1][1]['mosi'].nodes()) # chip ids of known mosi nodes
list(controller.network[1][1]['miso_us'].nodes()) # chip ids of known miso_us nodes
list(controller.network[1][1]['miso_ds'].nodes()) # chip ids of known miso_ds nodes
controller.network[1][1]['miso_us'].nodes[5] # attributes associated with node 5
controller.add_chip('1-1-6', version=2, root=True)
list(controller.network[1][1]['miso_us'].nodes()) # [5, 6]
```

The 'root' node is used to indicate which chips should be brought up first when
initializing the network.

Accessing connections between nodes is done via edges:

```python
list(controller.network[1][1]['miso_us'].edges()) # []
controller.add_network_link(1,1,'miso_us',(6,5),0) # link chips 6 -> 5 in the miso_us graph via chip 6's uart channel 0
list(controller.network[1][1]['miso_us'].edges()) # [(6,5)] direction indicates the data flow direction
controller.network[1][1]['miso_us'].edges[(6,5)] # attributes associated with link ('uart': 0)
```

In order to set up a 'working' network, you'll need to add the proper links in
the miso_ds and mosi graphs as well.

```python
controller.add_network_link(1,1,'miso_ds',(5,6),2)
controller.add_network_link(1,1,'mosi',(6,5),0)
controller.add_network_link(1,1,'mosi',(5,6),2)
```

External systems (e.g. the fpga you are using to communicate with the chips) are
conventionally called ``'ext0', 'ext1', ...`` and shouldn't be forgotten in the
network configuration! These nodes are used to determine the miso/mosi
configuration for the linked chips.

```python
controller.add_network_link(1,1,'mosi',('ext',6),1) # link chip 6 to 'ext' via chip 6's uart channel 0
controller.add_network_link(1,1,'miso_ds',(6,'ext'),1) # same for miso_ds
list(controller.network[1][1]['miso_ds'].edges())
list(controller.network[1][1]['mosi'].edges())
```

To then initialize a component on the network, run `controller.init_network(1,1,6)`.
This will modify the correct registers of chip 1-1-6 and send the configuration
commands to the system.

```python
controller.init_network(1,1,6)
controller.init_network(1,1,5)
```

Keep in mind, the order in which you initialize the network is important (e.g.
chip 6 needs to be initialized before chip 5 since it is upstream from chip 6).

You may also reset a particular node with `reset_network(<io_group>,<io_channel>,<chip_id>)`
which resets the network configuration of a particular node.

```python
controller.reset_network(1,1,5)
controller.reset_network(1,1,6)
```

This is all rather tedious, so there a few shortcuts to make declaring and
configuring the network easier. If you don't want to initialize or reset each
node in order, you may allow the controller to figure out the proper order
(based on the root nodes) and configure all of the chips.

```python
controller.init_network(1,1) # configure the 1-1 network
controller.reset_network(1,1) # revert the 1-1 network to it's original state
```

You may also specify a network configuration file and use this to create all
of the necessary network links and chips. See the
[docs](https://larpix-control.readthedocs.io/en/stable/api/configs/controller.html)
for how to create one of these files. This is the generally recommended means of
creating and loading a Hydra io network.

```python
# as an example for bringing up a hydra network from a config file
controller.load('<network config file>.json') # load your network and chips
for io_group, io_channels in controller.network.items():
    for io_channel in io_channels:
        controller.init_network(io_group, io_channel) # update configurations and write to chips
```

### Adjust the configuration of the LArPix Chips

Each Chip object manages its own configuration in software.
Configurations can be adjusted by name using attributes of the Chip's
configuration:

```python
chip5.config.threshold_global = 35  # entire register = 1 number
chip5.config.enable_periodic_reset = 1  # one bit as part of a register
chip5.config.channel_mask[20] = 1  # one bit per channel
```

Values are validated, and invalid values will raise exceptions.

Note: Changing the configuration of a Chip object does *not* change the
configuration on the ASIC.

Once the configuration is set, the new values must be sent to the LArPix
ASICs. There is an appropriate Controller method for that:

```python
controller.write_configuration(chip_key)  # send all registers
controller.write_configuration(chip_key, 32)  # send only register 32
controller.write_configuration(chip_key, [32, 50])  # send registers 32 and 50
```

Register addresses can be looked up using the configuration object:

```python
threshold_global_reg = chip5.config.register_map['threshold_global']
```

And register names:

```python
threshold_global_name = chip.5.config.register_map_inv[64]
```

For configurations which extend over multiple registers, the relevant
attribute will end in ``_addresses``. Certain configurations share a
single register, whose attribute has all of the names in it. View the
documentation or source code to find the name to look up. (Or look at
the LArPix data sheet.)

### Reading the configuration from LArPix ASICs

The current configuration state of the LArPix ASICs can be requested by
sending out "configuration read" requests using the Controller:

```python
controller.read_configuration(chip_key)
```

The same variations to read only certain registers are implemented for
reading as for writing.

The responses from the LArPix ASICs are stored for inspection. See the
section on "Inspecting received data" for more.

FakeIO queue code:

```python
packets = chip5.get_configuration_read_packets()
bytestream = b'bytes for the config read packets'
controller.io.queue.append((packets, bytestream))
```

### Receiving data from LArPix ASICs

When it is first initialized, the LArPix Controller ignores and discards
all data that it receives from LArPix. The Controller must be activated
by calling ``start_listening()``. All received data will then be
accumulated in an implementation-dependent queue or buffer, depending
on the IO interface used. To read the data from the buffer, call the
controller's ``read()`` method, which returns both the raw bytestream
received as well as a list of LArPix Packet objects which have been
extracted from the bytestream. To stop listening for new data, call
``stop_listening()``. Finally, to store the data in the controller
object, call the ``store_packets`` method. All together:

```python
controller.start_listening()
# Data arrives...
packets, bytestream = controller.read()
# More data arrives...
packets2, bytestream2 = controller.read()
controller.stop_listening()
message = 'First data arrived!'
message2 = 'More data arrived!'
controller.store_packets(packets, bytestream, message)
controller.store_packets(packets, bytestream2, message2)
```

There is a common pattern for reading data, namely to start listening,
then check in periodically for new data, and then after a certain amount
of time has passed, stop listening and store all the data as one
collection. The method ``run(timelimit, message)`` accomplishes just this.

```python
duration = 10  # seconds
message = '10-second data run'
controller.run(duration, message)
```

FakeIO queue code for the first code block:

```python
packets = [Packet_v2()] * 40
bytestream = b'bytes from the first set of packets'
controller.io.queue.append((packets, bytestream))
packets2 = [Packet_v2()] * 30
bytestream2 = b'bytes from the second set of packets'
controller.io.queue.append((packets2, bytestream2))
```

fakeIO queue code for the second code block:

```python
packets = [Packet_v2()] * 5
bytestream = b'[bytes from read #%d] '
for i in range(100):
    controller.io.queue.append((packets, bytestream%i))
```

### Inspecting received data

Once data is stored in the controller, it is available in the ``reads``
attribute as a list of all data runs. Each element of the list is a
PacketCollection object, which functions like a list of Packet objects
each representing one LArPix packet.

PacketCollection objects can be indexed like a list:

```python
run1 = controller.reads[0]
first_packet = run1[0]  # Packet object
first_ten_packets = run1[0:10]  # smaller PacketCollection object

first_packet_bits = run1[0, 'bits']  # string representation of bits in packet
first_ten_packet_bits = run1[0:10, 'bits']  # list of strings
```

PacketCollections can be printed to display the contents of the Packets
they contain. To prevent endless scrolling, only the first ten and last ten
packets are displayed, and the number of omitted packets is noted. To
view the omitted packets, use a slice around the area of interest.

```python
print(run1)  # prints the contents of the packets
print(run1[10:30])  # prints 20 packets from the middle of the run
```

In interactive Python, returned objects are not printed, but rather
their "representation" is printed (cf. the ``__repr__`` method). The
representation of PacketCollections is a listing of the number of
packets, the "read id" (a.k.a. the run number), and the message
associated with the PacketCollection when it was created.

### Individual LArPix Packets

LArPix Packet objects represent individual LArPix UART packets. They
have attributes which can be used to inspect or modify the contents of
the packet.

```python
packet = run1[0]
# all packets
packet.packet_type  # unique in that it gives the bits representation
packet.chip_id  # all other properties return Python numbers
packet.chip_key # key for association to a unique chip (can be None)
packet.parity
packet.downstream_marker

# data packets
packet.channel_id
packet.dataword
packet.timestamp
packet.trigger_type
packet.local_fifo
packet.shared_fifo
# config packets
packet.register_address
packet.register_data

# if fifo_diagnostics enabled on a given chip the timestamp of data packets
# are interpreted differently (note that this is not done automatically and will
# need to be performed manually on each packet)
packet.fifo_diagnostics_enabled = True
packet.timestamp
packet.local_fifo_events
packet.shared_fifo_events

```

Internally, packets are represented as an array of bits, and the
different attributes use Python "properties" to seamlessly convert
between the bits representation and a more intuitive integer
representation. The bits representation can be inspected with the
``bits`` attribute.

Packet objects do not restrict you from adjusting an attribute for an
inappropriate packet type. For example, you can create a data packet and
then set ``packet.register_address = 5``. This will adjust the packet
bits corresponding to a configuration packet's "register\_address"
region, which is probably not what you want for your data packet.

Packets have a parity bit which enforces odd parity, i.e. the sum of
all the individual bits in a packet must be an odd number. The parity
bit can be accessed as above using the ``parity`` attribute.
The correct parity bit can be computed using ``compute_parity()``,
and the validity of a packet's parity can be checked using
``has_valid_parity()``. When constructing a new packet, the correct
parity bit can be assigned using ``assign_parity()``.

Individual packets can be printed to show a human-readable
interpretation of the packet contents. The printed version adjusts its
output based on the packet type, so a data packet will show the data
word, timestamp, etc., while a configuration packet will show the register
address and register data.

Like with PacketCollections, Packets also have a "representation" view
based on the bytes that make up the packet. This can be useful for
creating new packets since a Packet's representation is also a vaild
call to the Packet constructor. So the output from an interactive
session can be copied as input or into a script to create the same
packet.

### Logging communications with LArPix ASICs using the HDF5Logger

To create a permanent record of communications with the LArPix ASICs, an
`HDF5Logger` is used. To create a new logger

```python
from larpix.logger import HDF5Logger
controller.logger = HDF5Logger(filename=None, buffer_length=10000) # a filename of None uses the default filename formatting
controller.logger.enable() # starts tracking all communications
```

You can also initialize and enable the logger in one call by passing the
``enabled`` keyword argument (which defaults to ``False``):

```
controller.logger = HDF5Logger(filename=None, enabled=True)
```

Now whenever you send or receive packets, they will be captured by the logger
and added to the logger's buffer. Once `buffer_length` packets have been
captured the packets will be written out to the file. You can force the logger
to dump the currently held packets at any time using `HDF5Logger.flush()`

```python
controller.verify_configuration()
controller.logger.flush()
```

In the event that you want to temporarily stop tracking communications,
the `disable` and `enable` commands do exactly what you think they might.

```python
controller.logger.disable() # stop tracking
# any communication here is ignored
controller.logger.enable() # start tracking again
controller.logger.is_enabled() # returns True if tracking
```

Once you have finished your tests, be sure to disable the logger. If you do not,
you will lose any data still in the buffer of the logger object. We strongly recommend
wrapping logger code with a `try, except` statement if you can. Any remaining
packets in the buffer are flushed to the file upon disabling.

```python
controller.logger.disable()
```

### Viewing data from the HDF5Logger

The ``HDF5Logger`` uses a format called LArPix+HDF5v1.0 that is specified in
the ``larpix.format.hdf5format`` module (and
[documentation](https://larpix-control.readthedocs.io/en/stable/)
starting in v2.3.0). That module contains a ``to_file`` method which is
used internally by ``HDF5Logger`` and a ``from_file`` method that you
can use to load the file contents back into LArPix Control. The
LArPix+HDF5 format is a "plain HDF5" format that can be inspected with
``h5py`` or any language's HDF5 binding.

To open the HDF5 file from python

```python
import h5py
datafile = h5py.File('<filename>')
```

Within the datafile there is one group (`'_header'`) and two datasets
(``'packets'`` and ``'messages'``). The header group contains some useful meta information about
when the datafile was created and the file format version number, stored as
attributes.

```python
list(datafile.keys()) # ['_header', 'messages', 'packets']
list(datafile['_header'].attrs) # ['created', 'modified', version']
```

The packets are stored sequentially as a `numpy` mixed-type arrays within the
rows of the HDF5 dataset. The columns refer to the element of the numpy mixed
type array. The specifics of the data type and entries are set by the
``larpix.format.hdf5format.dtype`` object - see the larpix-control docs for more information.
You can inspect a packet as a tuple simply by accessing its respective position within the
HDF5 dataset.

```python
raw_value = datafile['packets'][0] # e.g. (b'0-246', 3, 246, 1, 1, -1, -1, -1, -1, -1, -1, 0, 0)
raw_values = datafile['packets'][-100:] # last 100 packets in file
```

If you want to make use of `numpy`'s mixed type arrays, you can convert the
raw values to the proper encoding by retrieving it as a list (of length
1, for example) via

```python
packet_repr = raw_values[0:1] # list with one element
packet_repr['chip_key'] # chip key for packet, e.g. b'1-1-246'
packet_repr['adc_counts'] # list of ADC values for each packet
packet_repr.dtype # description of data type (with names of each column)
```

You can also view entire "columns" of data:

```python
# all packets' ADC counts, including non-data packets
raw_values['adc_counts']
# Select based on data type using a numpy bool / "mask" array:
raw_values['adc_counts'][raw_values['type'] == 0] # all data packets' ADC counts
```

``h5py`` and ``numpy`` optimize the retrieval of data so you can read
certain columns or rows without loading the entire data file into memory.

Don't forget to close the file when you are done. (Not necessary in
interactive python sessions if you are about to quit.)

```python
datafile.close()
```

## Running with a Bern DAQ board (v1 asic)

Since you have completed the tutorial with the `FakeIO` class, you are now ready
to interface with some LArPix ASICs. If you have a Bern DAQ v2-3 setup you can
follow along with the rest of the tutorial.

Before you can configure the system, you will need to generate a configuration
file for the ZMQ_IO or MultiZMQ_IO interface. This provides the mapping from
chip keys to physical devices. In the case of the ZMQ interface, it maps
io group #s to the IP address of the DAQ board. A number of example
configurations are provided in the installation under
``larpix/configs/io/<config name>.json``, which may work for your purposes. We
recommend reading the docs about how to create one of these configuration files.
By default the system looks for configuration in the pwd, before looking for the
installation files. If you only have one DAQ board on your network, likely
you will load the ``io/daq-srv<#>.json`` configuration.

With the DAQ system up and running
```python
>>> from larpix import Controller
>>> from larpix.io import ZMQ_IO
>>> controller = Controller()
>>> controller.io = ZMQ_IO(config_filepath='<path to config>')
>>> controller.load('controller/pcb-<#>_chip_info.json')
>>> controller.io.ping()
>>> for key,chip in controller.chips.items():
...     chip.config.load('chip/quiet.json')
...     print(key, chip.config)
...     controller.write_configuration(key)
>>> controller.run(1,'checking the data rate')
>>> controller.reads[-1]
<PacketCollection with 0 packets, read_id 0, 'checking the data rate'>
```
This should give you a quiet state with no data packets. Occasionally, there can
be a few packets left in one of the system buffers (LArPix, FPGA, DAQ server). A
second run command should return without any new packets.

If you are using the v1.5 anode, you may need to reconfigure the miso/mosi mapping (since the miso/mosi pair for a daisy chain is not necessarily on a single channel). To do this, pass a `miso_map` or `mosi_map` to the `ZMQ_IO` object on initialization:
```python
>>> controller.io = ZMQ_IO(config_filepath='<path to config>', miso_map={2:1}) # relabels packets received on channel 2 as packets from channel 1
```

### Check configurations
If you are still receiving data, you can check that the hardware chip configuration
match the software chip configurations with
```python
>>> controller.verify_configuration()
(True, {})
```
If the configuration read packets don't match the software chip configuration, this
will return
```python
>>> controller.verify_configuration()
(False, {<register>: (<expected>, <received>), ...})
```
Missing packets will show up as
```python
>>> controller.verify_configuration()
(False, {<register>: (<expected>, None), ...})
```
If your configurations match, and you still receive data then you are likely seeing
some pickup on the sensor from the environment -- *good luck!*

### Enable a single channel
```python
>>> chip_key = '1-1-3'
>>> controller.disable() # mask off all channel
>>> controller.enable(chip_key, [0]) # enable channel 0 of chip
```

### Set the global threshold of a chip
```python
>>> controller.chips[chip_key].config.global_threshold = 40
>>> controller.write_configuration(chip_key)
>>> controller.verify_configuration(chip_key)
(True, {})
```

### Inject a pulse into a specific channel
```python
>>> controller.enable_testpulse(chip_key, [0]) # connect channel 0 to the test pulse circuit and initialize the internal DAC to 255
>>> controller.issue_testpulse(chip_key, 10) # inject a pulse of size 10DAC by stepping down the DAC
<PacketCollection with XX packets, read_id XX, "configuration write">
>>> controller.disable_testpulse(chip_key) # disconnect test pulse circuit from all channels on chip
```
You will need to periodically reset the DAC to 255, otherwise you will receive a
`ValueError` once the DAC reaches the minimum specified value.
```python
>>> controller.enable_testpulse(chip_key, [0], start_dac=255)
>>> controller.issue_testpulse(chip_key, 50, min_dac=200) # the min_dac keyword sets the lower bound for the DAC (useful to avoid non-linearities at around 70-80DAC)
<PacketCollection with XX packets, read_id XX, "configuration write">
>>> controller.issue_testpulse(chip_key, 50, min_dac=200)
ValueError: Minimum DAC exceeded
>>> controller.enable_testpulse(chip_key, [0], start_dac=255)
>>> controller.issue_testpulse(chip_key, 50, min_dac=200)
<PacketCollection with XX packets, read_id XX, "configuration write">

```

### Enable the analog monitor on a channel
```python
>>> controller.enable_analog_monitor(chip_key, 0) # drive buffer output of channel 0 out on analog monitor line
>>> controller.disable_analog_monitor(chip_key) # disable the analog monitor on chip
```
While the software enforces that only one channel per chip is being driven out on
the analog monitor, you must disable the analog monitor if moving between chips.


## Miscellaneous implementation details

### Endian-ness

We use the convention that the LSB is sent out first and read in first.
The location of the LSB in arrays and lists changes from object to
object based on the conventions of the other packages we interact with.

In particular, pyserial sends out index 0 first, so for `bytes` objects,
index 0 will generally have the LSB. On the other hand, bitstrings
treats the _last_ index as the LSB, which is also how numbers are
usually displayed on screen, e.g. `0100` in binary means 4 not 2. So for
`BitArray` and `Bits` objects, the LSB will generally be last.

Note that this combination leads to the slightly awkward convention that
the least significant bit of a bytestring is the *last bit* of the
*first byte*. For example, if bits[15:0] of a packet are
`0000 0010 0000 0001` ( = 0x0201 = 513), then the bytes will be sent out as
`b'\x01\x02'`.

### The Configuration object

The `Configuration` object represents all of the options in the LArPix
configuration register. Each row in the configuration table in the LArPix datasheet
has a corresponding attribute in the `Configuration` object. Per-channel
attributes are stored in a list, and all other attributes are stored as
a simple integer. (This includes everything from single bits to values
such as "reset cycles," which spans 3 bytes.)

`Configuration` objects also have some helper methods for enabling and
disabling per-channel settings (such as `csa_testpulse_enable` or
`channel_mask`). The relevant methods are listed here and should be
prefixed with either `enable_` or `disable_`:

 - `channels` enables/disables the `channel_mask` register
 - `external_trigger` enables/disables the `external_trigger_mask`
    register
 - `testpulse` enables/disables the `csa_testpulse_enable` register
 - `analog_monitor` enables/disables the `csa_monitor_select` register

Most of these methods accept an optional list of channels to enable or
disable (and with no list specified acts on all channels). The exception
is `enable_analog_monitor` (and its `disable` counterpart): the `enable`
method requires a particular channel to be specified, and the `disable`
method does not require any argument at all. This is because at most one
channel is allowed to have the analog monitor enabled.

The machinery of the `Configuration` object ensures that each value is
converted to the appropriate set of bits when it comes time to send
actual commands to the physical chip. Although this is not transparent
to you as a user of this library, you might want to know that two sets of
configuration options are always sent together in the same configuration
packet:

 - `csa_gain`, `csa_bypass`, and `internal_bypass` are combined into a
   single byte, so even though they have their own attributes, they must
   be written to the physical chip together

 - `test_mode`, `cross_trigger_mode`, `periodic_reset`, and
   `fifo_diagnostic` work the same way

Similarly, all of the per-channel options (except for the pixel trim
thresholds) are sent in 4 groups of 8 channels.

Configurations can be loaded by importing `larpix.configs` and running
the `load` function. This function searches for a configuration with the
given filename relative to the current directory before searching the
"system" location (secretly it's in the larpix/configs/ folder). This is
similar to `#include "header.h"` behavior in C.

Configurations can be saved by calling `chip.config.write` with the
desired filename.

Once the Chip object has been configured, the configuration must be sent
to the physical chip.

