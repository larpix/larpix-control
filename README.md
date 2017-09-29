# larpix-control

Control the LArPix chip using the FTDI D2XX driver library.

### Setup and installation

Download the D2XX library from FTDI's website. Make sure libftd2xx.so is
in your LD\_LIBRARY\_PATH or other search path, and ftd2xx.h and
WinTypes.h are in a directory called ftd2xx in your include path. Example locations are
/usr/local/lib/libftd2xx.so and /usr/local/include/ftd2xx/ftd2xx.h and
WinTypes.h.

Download this repository.

To generate the larpix.o file and a demonstration executable just run
`make`.

### Tutorial

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

By the way, you can access the low-level `FT_HANDLE` structure using
`c.ft_handle`. Leave it alone, though, for your own good.

Next you might want to write some data to the chip. To facilitate
bitstreams and bytestreams, there is a data structure called
`larpix_data`. To create one, use

```C
larpix_data data;
larpix_data_init(&data);
```

You can set each of the 8 bitstreams individually. For example, if you
have an array `ch0` that contains the bits for channel 0, you can add it
to the bytestream using

```C
larpix_data_set_bitstream(&data, ch0, 0, length);
```

If the length of the array is longer than the maximum allowed
(`LARPIX_BUFFER_SIZE`), then the transcribed data will be truncated.

There are a few type shorthands which can make things easier. You can
use `byte` for a single byte (it's aliased to `unsigned char`, or `BYTE`
in D2XX). And `uint` for `unsigned int`, or `DWORD` in D2XX.
