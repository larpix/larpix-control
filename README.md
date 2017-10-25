# larpix-control

Control the LArPix chip

[![Documentation Status](https://readthedocs.org/projects/larpix-control/badge/?version=latest)](http://larpix-control.readthedocs.io/en/latest/?badge=latest)

## Setup and installation

This code is intended to work on both Python 2.7+ and Python 3.6+,
but it was designed in Python 3 and is not guaranteed to work in
Python 2.

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
functions. I imagine they will also come in handy when you're confused
about the bit order. (Also see the section on endian-ness below.)

## Tutorial

This tutorial runs through how to use all of the main functionality of
larpix-control.

To access the package contents, use one of the two following `import`
statements:

```python
import larpix.larpix as larpix  # use the larpix namespace
# or ...
from larpix.larpix import *  # import all larpix classes into the current namespace
```

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

### Creating a LArPix Chip

The `Chip` object represents a single LArPix chip and knows about
everything happening on the chip regarding configuration, data sent in,
and data read out. To create a Chip, just provide the chip ID number
(hard-wired into the PCB) and the index for the IO Chain (daisy chain)
that the chip is part of:

```python
myChip = Chip(100, 0)
```

The Chip object uses these ID values when it creates data packets to
ensure that the packet reaches the correct chip. And other objects use
the ID values to ensure that received data from the physical chip makes
its way to the right Chip object.

The chip's configuration register is represented by the `myChip.config`
attribute, which is an instance of the `Configuration` object.

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

Once the Chip object has been configured, the configuration must be sent
to the physical chip. This is accomplished with the `Controller` object,
which we'll discuss next.

### Communicating with the physical LArPix chip

Communication between the computer and the physical LArPix chip is
handled by the `Controller` object and uses a Serial interface. (The
interface specification is given in the fpga\_interface.txt file. It's
based on RS-232 8N1.) To initialize a Controller object, simply provide
the port you'd like to communicate over. For the envisioned normal
application (with an FTDI chip as USB-serial bridge), this will likely
be something like `/dev/ttyUSB0`.

```python
controller = Controller('/dev/ttyUSB0')
```

An important attribute of the Controller object is `chips`, which is a
list of Chip objects controlled by the particular Controller. Add a
single Chip object to the list with `controller.chips.append(myChip)`,
or add a whole list with `controller.chips.extend(list_of_chips)`.

You might want to change the following
attributes at some point, but their defaults should work in most cases:

 - `baudrate`: default = 1000000 baud. Controls the number of bits per
   second, including RS-232 start and stop bits.
 - `timeout`: default = 1 second. Controls how long to wait before
   ending a read command
 - `max_write`: default = 8192 bytes. Controls the maximum number of
   bytes to send with a single write command. The limit is entirely due
   to the buffer capacity of the FTDI chip.

#### Sending data

The only data that LArPix can receive is configuration data. To send all
of the configuration packets in write mode, simply call

```python
myChip = Chip(chip_id, io_chain)
# Edit the configuration
# ...
myController = Controller('/dev/ttyUSB0')
myController.write_configuration(myChip)
```

To send only a particular configuration register or list of
configuration registers, pass the register or list of registers to the
function:

```python
register_to_update = 51
myController.write_configuration(myChip, register_to_update)
# or pass a list ...
registers_to_update = [0, 5, 42]
myController.write_configuration(myChip, registers_to_update)
```

There is currently not a way to specify which register to update by
passing a string or other way of identifying the register by name.

Similar functionality exists to read the configuration data. This
requires both sending data to and receiving data from the LArPix chip.
To send the "read configuration" commands, call `read_configuration`
exactly the same way you would call `write_configuration`. Read on to
learn about receiving data from LArPix in more detail.

#### Receiving data

There are 3 reasons to receive data from LArPix: because it's real data
(ADC counts, etc.), because it's configuration data that has been
requested, or because it's test data from either the UART test or the
FIFO test.

The simplest way to receive data from LArPix is to just listen for a
certain amount of time and save all the packets received. This is
accomplished with the `run` method:

```python
myController.run(10)  # listens for 10 seconds
```

This method makes sense for physics runs or any special runs that aren't
provided by the following other methods.

To read configuration data, call `read_configuration`, as mentioned
earlier.

To make it easy to run tests, the following methods will configure the
chip, run the test, and record the data received: `run_testpulse`,
`run_fifo_test`, and `run_analog_monitor_test`.

#### Accessing received data

Every method that reads data processes the data from a bytestream into a
Packet object. The Packet objects are appended to the list stored in the
`reads` attribute of the correct Chip object, as defined by the `chipid`
returned by the Packet. It's worth noting here that the Controller
object is only aware of Chip objects listed in the `controller.chips`
attribute.
