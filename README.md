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
larpix_write_data_loop(&c, &data, num_loops, length);
```

This command will write the first `length` bytes of data in
`data` to the FTDI chip repeatedly, `num_loops` times.

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
