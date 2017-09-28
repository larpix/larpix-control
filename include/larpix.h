#include <ftd2xx/ftd2xx.h>

typedef unsigned int uint;
typedef unsigned char byte;

#define LARPIX_BUFFER_SIZE 1024

typedef struct larpix_connection
{
    FT_HANDLE ft_handle;
    int port_number;
    uint clk_divisor;
    byte pin_io_directions;
    byte bit_mode;
    uint timeout;
    uint usb_transfer_size;
    byte output_buffer[LARPIX_BUFFER_SIZE];
} larpix_connection;

void larpix_default_connection(larpix_connection* c);
int larpix_connect(larpix_connection* c);
int larpix_disconnect(larpix_connection* c);
int larpix_configure_ftdi(larpix_connection* c);
uint larpix_write_zeros_loop(larpix_connection* c, uint num_loops);
