#include <ftd2xx/ftd2xx.h>

typedef unsigned int uint;
typedef unsigned char byte;

#define LARPIX_BUFFER_SIZE 1024

typedef struct larpix_data
{
    byte bits[8][LARPIX_BUFFER_SIZE];
} larpix_data;
typedef struct larpix_connection
{
    FT_HANDLE ft_handle;
    int port_number;
    uint clk_divisor;
    byte pin_io_directions;
    byte bit_mode;
    uint timeout;
    uint usb_transfer_size;
    larpix_data output_data;
} larpix_connection;


void larpix_default_connection(larpix_connection* c);
int larpix_connect(larpix_connection* c);
int larpix_disconnect(larpix_connection* c);
int larpix_configure_ftdi(larpix_connection* c);
uint larpix_write_data_loop(larpix_connection* c, uint num_loops);

void larpix_data_init(larpix_data* data);
void larpix_data_to_array(larpix_data* data, byte* array, uint nbytes);
void larpix_array_to_data(larpix_data* data, byte* array, uint nbytes);
void larpix_data_set_bitstream(larpix_data* data,
        byte* array,
        uint bit_position,
        uint nbytes);
void larpix_data_get_bitstream(larpix_data* data,
        byte* array,
        uint bit_position,
        uint nbytes);
