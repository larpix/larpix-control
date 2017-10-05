# larpix-control

Control the LArPix chip using the FTDI D2XX driver library.

## Setup and installation

Download the D2XX library from FTDI's website. Make sure libftd2xx.so is
in your LD\_LIBRARY\_PATH or other search path, and ftd2xx.h and
WinTypes.h are in a directory called ftd2xx in your include path. Example locations are
/usr/local/lib/libftd2xx.so and /usr/local/include/ftd2xx/ftd2xx.h and
WinTypes.h.

Download this repository.

To generate the larpix.o file and a demonstration executable just run
`make`.

## Tutorial

You're probably also looking for the Python interface. That's after the C
tutorial.

### Connecting to the FTDI chip

The fundamental data structure is the `larpix_connection`. You can
initialize the data structure with

```C
larpix_connection c;
larpix_default_connection(&c);
```

To connect to the FTDI chip, you might have to change `c.port_number`
from its default of `0`. Usually this is not an issue. You also can
change various configuration options including `pin_io_directions`,
`bit_mode`, `clk_divisor`, `timeout`, and `usb_transfer_size`.

The code to open a connection to and configure the FTDI chip is:

```C
larpix_connect(&c);
larpix_configure_ftdi(&c);
```

When you're done, you'll want to disconnect from the chip. You can do
that with

```C
larpix_disconnect(&c);
```

By the way, you can access the low-level `FT_HANDLE` structure using
`c.ft_handle`. Leave it alone, though, for your own good.

### Handling data to send to the chip

Next you might want to write some data to the chip. The D2XX software
accepts as input an array of bytes called a bytestream. Within a byte,
the different bits correspond to different pins on the chip. Each byte
corresponds to one timestep. The collection of all of the bits in the
same position at each element of the bytestream is a bitstream. A
bytestream has 8 bitstreams.

To facilitate bitstreams and bytestreams, there is a data structure
called `larpix_data`. Usually you will want to initialize all bitstreams
to 1 (high) because of the UART interface. You can also set one of the
channels to be a clock (clk).

```C
larpix_data data;
larpix_data_init_high(&data); // or init_low
larpix_data_set_clk(&data, 0); // clk on channel 0
```

You can set each of the 8 bitstreams individually. For example, if you
have an array `ch3` that contains the bitstream for channel 3, you can
write it to the bytestream using

```C
larpix_data_set_bitstream(&data, ch3, 3, length); // Separate object
```

If the length of the array is longer than the maximum allowed
(`LARPIX_BUFFER_SIZE`), then the transcribed data will be truncated.

There are a few type shorthands which can make things easier. You can
use `byte` for a single byte (it's aliased to `unsigned char`, or `BYTE`
in D2XX). And `uint` for `unsigned int`, or `DWORD` in D2XX.

If you already have a bytestream in an array and want to load it into
the `larpix_data` struct, or you want to extract the bytestream from
`larpix_data`, use

```C
larpix_array_to_data(&data, bytestream_array, length); // load in bytestream
larpix_data_to_array(&data, bytestream_array, length); // extract bytestream
```

### Sending data to the chip

Once you have set up the `larpix_data` with your bytestream, you can
send it to the chip with

```C
larpix_write_data(&c, &data, 1, length);
```

This command will write the first `length` bytes of data in
`data` to the FTDI chip repeatedly, `num_loops` times.

You might wonder what the `1` argument is for. Well, if you have a whole
set of `larpix_data` in an array (e.g. `larpix_data array[10];`), and
you want to write them out in quick succession, you're in luck!

```C
larpix_write_data(&c, data_array, array_size, length);
```

This is the absolute fastest that data can be written to the FTDI chip.

### Reading data from the chip

To read data from the chip, first decide how many data blocks you want
to read. Create an array of `larpix_data` with size equal to the number
of blocks to read. Then you can read with

```C
larpix_read_data(&c, data_array, array_size, length);
```

This command will read `length` bytes from the FTDI into each
`larpix_data` and is the fastest that data can be read from the FTDI
chip.

### Reading and writting in quick succession

It will be extremely useful to read and write in quick succession, not
only when querying the configuration status or when using the LArPix
test mode, but also in normal operation since we must write out the
clock and a constant high signal on the UART line. This function will
write first and then read, repeatedly and in quick succession. Assuming
you have an array of `larpix_data` to read and another array to write,
you can do the following.

```C
uint total_bytes_written;
uint total_bytes_read;
larpix_write_read_data(&c, write_array, read_array,
    1, // number of write-read pairs
    length_write, // number of bytes per write
    length_read, // number of bytes per read
    &total_bytes_written, // will be filled with total bytes written
    &total_bytes_read); // will be filled with total bytes read
```

This is the fastest possible read-write configuration.

### Handling UART data format

All communication to and from the LArPix chip is in 54-bit UART (plus a
start bit and a stop bit). To aid in the construction and interpretation
of these UART words, use `larpix_uart_packet`. Each section of the UART
packet has a corresponding getter and setter.

```C
larpix_uart_packet packet;

// Packet type
larpix_uart_set_packet_type(&packet, LARPIX_PACKET_DATA);
larpix_uart_set_packet_type(&packet, LARPIX_PACKET_CONFIG_WRITE);
larpix_packet_type type = larpix_uart_get_packet_type(&packet);

// Parity bit
larpix_uart_set_parity(&packet); // computes automatically
uint parity = larpix_uart_compute_parity(&packet);
uint status = larpix_uart_check_parity(&packet); // 0 -> good, 1-> error
```

There is a getter/setter for every section of the UART packet that is
described in Section 5.4 of the LArPix Datasheet (v2).


To communicate with the chip, `larpix_uart_packet` must be converted
to/from `larpix_data`. The functions also return a status value which is
nonzero if there is not enough space in the `larpix_data` to fit all the
bits of the packet. Note for both data-to-uart and uart-to-data functions,
the `startbit` parameter gives the location of the UART start bit, _not_
the first bit of the 54-bit word.

```C
// To prepare to write to chip
// Include which data stream (e.g. pin 1) and
// where along the bitstream the UART start bit should go (e.g. 128)
uint status = larpix_uart_to_data(&packet, &data, 1, 128); // 0->good, 1->error
uint status = larpix_data_to_uart(&packet, &data, 1, 128); // 0->good, 1->error
```

The `larpix_uart_to_data` function dilates the data by a factor of
4 to account for the relationship between the master clock and the
UART baudrate. This feature will likely change depending on the final
communication setup between the C code and the LArPix chip.

### Chip configuration

First: the configuration layout is a bit complicated. So bear with me.

To configure the LArPix chip upon startup, three things need to happen:

  1. You need to decide on a configuration

  2. That configuration needs to be written to a large number of UART
     packets (currently 63), with the caveats that

     - some configurations occupy multiple registers/bytes so must be
       sent on multiple UART packets

     - some configurations are only a bit or two and are combined with
       other configuration values onto a single register/byte, so are
       sent together on the same UART packet

  3. Those packets must all be sent to the chip

For subsequent configurations, e.g. to enable then disable test mode,
keeping everything else the same, only the UART packets corresponding to
the changed configuration values need to be created and then sent.

The data structure that keeps track of a chip's configuration is the
`larpix_configuration` struct. Initialize it to the LArPix chip's
default values using

```C
larpix_configuration config;
larpix_config_init_defaults(&config);
```

You can then access the struct's members to adjust the configuration.
View the larpix.h header file to see all of the members. They are named
to match the list in Section 5.2 of the LArPix datasheet, and they are
in the same order in the header file as in that list.

A small technicality is that `test_burst_length` and `reset_cycles` both
use more than a byte to store a number, and are represented by an array
of bytes. So you'll have to do the math yourself to get the number you
want. For example:

```C
config.test_burst_length[0] = 5;
config.test_burst_length[1] = 1; // value is 256 + 5 = 261
```

To transfer the complete configuration into a collection of UART
packets, use the `larpix_config_write_all` function:

```C
larpix_uart_packet full_config_packets[LARPIX_NUM_CONFIG_REGISTERS]; // [63]
larpix_config_write_all(&config, full_config_packets);
```

This function only adjusts the "register map address" and "register map
data" portions of the UART packet (i.e. calls `larpix_uart_set_register`
and `larpix_uart_set_register_data` but no other `larpix_uart`
functions).

There is a corresponding `larpix_config_read_all` function which
extracts the configuration from an array of UART packets into a
`larpix_configuration` object. It does not modify the packets at all,
but the array should be in "configuration register" order from 0 to 62.
This function also returns a "status" result which is `0` if all reads
are successful, else is the number of unsuccessful reads. (A possible
upgrade here is to specify which reads are unsuccessful. Don't hold your
breath though.) Unsuccessful reads happen when the "register map
address" in the UART packet does not match the expected address for the
particular configuration being read.

It is also possible to create UART packets one at a time, for only the
configuration values that you want to update. Each data member of the
`larpix_configuration` struct has its own
`larpix_config_write_X(config, uart_packet)` and
`larpix_config_read_X(config, uart_packet)` functions. Like with
`larpix_config_write_all`, these individual functions adjust the
register map address and register map data portions of the UART packet,
and the read functions are read-only. The read functions return 0 on
successful read and 1 on unsuccessful read.

```C
larpix_config_write_csa_testpulse_dac_amplitude(&config, &packet);

byte channel_chunk = 2;
uint status = larpix_config_read_csa_bypass_select(&config, &packet, channel_chunk);
```

As implied by the code example, there are a few subtleties.

 - `pixel_trim_thresholds` requires an additional parameter ,`channelid`

 - `csa_bypass_select`, `csa_monitor_select`, `csa_testpulse_enable`,
   `channel_mask`, and `external_trigger_mask` store only one bit per
   channel, and are squeezed into 4 bytes each. So the corresponding
   read/write functions require an additional parameter, `channel_chunk`,
   which ranges from 0 to 3 and determines which group of channels to
   write (0:7, 8:15, 16:23, or 24:31, respectively).

 - `test_burst_length` and `reset_cycles`, as mentioned above, combine
   more than 1 byte into a single number. The corresponding read/write
   functions require an additional parameter, `value_chunk`, which
   determines which byte is written.

 - `csa_gain`, `csa_bypass`, and `internal_bypass` are combined into a
   single byte, so there is only one read and one write function which
   includes all three settings, namely
   `larpix_config_write_csa_gain_and_bypasses` (and the corresponding
   read function).

 - `test_mode`, `cross_trigger_mode`, `periodic_reset`, and
   `fifo_diagnostic` are also combined into a single byte. Their
   combined function is `larpix_config_write_test_mode_xtrig_reset_diag`.

### Python interface

You can access all of the larpix-control functionality through
the Python interface. Simply import the larpix\_c.py module into
your program. Then you can access the struct types as python
classes with the same names as the corresponding C structs.
`larpix_packet_type` is a python dict with keys `data`, `test`,
`config_write`, and `config_read`. You can call any and all C functions
via `larpix_c.larpix.<function-name>`.


Here's an example:

```python
from larpix_c import *
import ctypes as c
conn = larpix_connection()
larpix.larpix_default_connection(c.byref(conn))
larpix.larpix_connect(c.byref(conn))
larpix.larpix_configure_ftdi(c.byref(conn))

packet = larpix_uart_packet()
larpix.larpix_uart_set_packet_type(c.byref(packet), larpix_packet_type['data'])
larpix.larpix_uart_set_parity(c.byref(packet))

data = larpix_data()
larpix.larpix_data_init_high(c.byref(data))
larpix.larpix_data_set_clk(c.byref(data), 0)  # can use python integer as c int
status = larpix.larpix_uart_to_data(c.byref(packet), c.byref(data), 1, 128)

larpix.larpix_write_data(c.byref(conn), c.byref(data), 1, LARPIX_BUFFER_SIZE)
```

Note: a more Pythonic wrapper is under development.
