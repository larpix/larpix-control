# larpix-control

Control the LArPix chip

[![Documentation Status](https://readthedocs.org/projects/larpix-control/badge/?version=latest)](http://larpix-control.readthedocs.io/en/latest/?badge=latest)
[![Build Status](https://travis-ci.com/samkohn/larpix-control.svg?branch=master)](https://travis-ci.com/samkohn/larpix-control)

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

## Minimal working example

So you're not a tutorials kind of person. Here's a minimal working
example for you to play around with:

```python
>>> import larpix.larpix as larpix
>>> from larpix.io.fakeio import FakeIO
>>> from larpix.logger.stdout_logger import StdoutLogger
>>> controller = larpix.Controller()
>>> controller.io = FakeIO()
>>> controller.logger = StdoutLogger(buffer_length=0)
>>> controller.logger.open()
>>> chip1 = controller.add_chip('0-1', 1)  # (access key, chipID)
>>> chip1.config.global_threshold = 25
>>> controller.write_configuration('0-1', 25) # chip key 1, register 25
[ Config write | Chip key: '0-1' | Chip: 1 | Register: 25 | Value:  16 | Parity: 1 (valid: True) ]
>>> packet = larpix.Packet(b'\x04\x14\x80\xc4\x03\xf2 ')
>>> packet_bytes = packet.bytes()
>>> pretend_input = ([packet], packet_bytes)
>>> controller.io.queue.append(pretend_input)
>>> controller.run(0.05, 'test run')
>>> print(controller.reads[0])
[ Data | Chip key: None | Chip: 1 | Channel: 5 | Timestamp: 123456 | ADC data: 120 | FIFO Half: False | FIFO Full: False | Parity: 1 (valid: True) ]
```

## Tutorial

This tutorial runs through how to use all of the main functionality of
larpix-control.

To access the package contents, use one of the two following `import`
statements:

```python
import larpix.larpix as larpix  # use the larpix namespace
# or ...
from larpix.larpix import *  # import all core larpix classes into the current namespace
```

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
controller = larpix.Controller()
controller.io = larpix.io.fakeio.FakeIO()
controller.logger = larpix.logger.stdout_logger.StdoutLogger(buffer_length=0)
controller.logger.open()
```

The ``FakeIO`` object imitates a real IO interface for testing purposes.
It directs its output to stdout (i.e. it prints the output), and it
takes its input from a manually-updated queue. At the end of each
relevant section of the tutorial will be code for adding the expected
output to the queue. You'll have to refill the queue each time you run
the code.

Similarly, the ``StdoutLogger`` mimics the real logger interface for testing. It
prints nicely formatted records of read / write commands to stdout every
``buffer_length`` packets. The logger interface requires opening or enabling the
logger before messages will be stored. Before ending the python session, every
logger should be closed to flush any remaining packets stored in the buffer.

### Set up LArPix Chips

Chip objects represent actual LArPix ASICs. For each ASIC you want to
communicate with, create a LArPix Chip object and add it to the
Controller.

```python
chipid = 5
chip_key = '0-5'
chip5 = controller.add_chip(chip_key, chipid)
chip5 = controller.get_chip(chip_key)
```

The `chip_key` field specifies the necessary information for the `controller.io`
object to route packets to/from the chip. The specifications for this field are
implemented separately in each `larpix.io` class.

### Adjust the configuration of the LArPix Chips

Each Chip object manages its own configuration in software.
Configurations can be adjusted by name using attributes of the Chip's
configuration:

```python
chip5.config.global_threshold = 35  # entire register = 1 number
chip5.config.periodic_reset = 1  # one bit as part of a register
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
global_threshold_reg = chip5.config.global_threshold_address
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
packets = chip5.get_configuration_packets(larpix.Packet.CONFIG_READ_PACKET)
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
packets = [Packet()] * 40
bytestream = b'bytes from the first set of packets'
controller.io.queue.append((packets, bytestream))
packets2 = [Packet()] * 30
bytestream2 = b'bytes from the second set of packets'
controller.io.queue.append((packets2, bytestream2))
```

fakeIO queue code for the second code block:

```python
packets = [Packet()] * 5
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
run1 = controller.runs[0]
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
packet.chipid  # all other properties return Python numbers
packet.chip_key # key for association to a unique chip
packet.parity_bit_value
# data packets
packet.channel_id
packet.dataword
packet.timestamp
packet.fifo_half_flag  # 1 or 0
packet.fifo_full_flag  # 1 or 0
# config packets
packet.register_address
packet.register_data
# test packets
packet.test_counter
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
bit can be accessed as above using the ``parity_bit_value`` attribute.
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
such as "reset cycles," which spans 3 bytes.) **Warning**: there is
currently no type checking or range checking on these values. Using
values outside the expected range will lead to undefined behavior,
including the possibility that Python will crash _or_ that LArPix will
be sent bad commands.

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

