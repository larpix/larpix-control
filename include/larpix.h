#ifndef LARPIX_H
#define LARPIX_H

#include <ftd2xx/ftd2xx.h>

typedef unsigned int uint;
typedef unsigned long ulong;
typedef unsigned char byte;

#define LARPIX_BUFFER_SIZE 1024
#define LARPIX_UART_SIZE 54

#define LARPIX_UART_PTYPE_LOW 0
#define LARPIX_UART_PTYPE_HIGH 1
#define LARPIX_UART_CHIPID_LOW 2
#define LARPIX_UART_CHIPID_HIGH 9
#define LARPIX_UART_PARITY 53

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
} larpix_connection;

typedef struct larpix_uart_packet
{
    byte data[LARPIX_UART_SIZE];
} larpix_uart_packet;

typedef enum larpix_packet_type
{
    LARPIX_PACKET_DATA,
    LARPIX_PACKET_TEST,
    LARPIX_PACKET_CONFIG_WRITE,
    LARPIX_PACKET_CONFIG_READ
} larpix_packet_type;

ulong larpix_bitstream_to_int(byte* bitstream, uint length);
void larpix_int_to_bitstream(byte* bitstream, ulong input, uint length);
void larpix_default_connection(larpix_connection* c);
int larpix_connect(larpix_connection* c);
int larpix_disconnect(larpix_connection* c);
int larpix_configure_ftdi(larpix_connection* c);
uint larpix_write_data_loop(larpix_connection* c,
        larpix_data* data,
        uint num_loops,
        uint nbytes);

void larpix_data_init_high(larpix_data* data);
void larpix_data_init_low(larpix_data* data);
void larpix_data_set_clk(larpix_data* data, uint bit_position);
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

uint larpix_uart_to_data(larpix_uart_packet* packet, larpix_data* data,
        uint bit_position,
        uint startbit);
uint larpix_data_to_uart(larpix_uart_packet* packet, larpix_data* data,
        uint bit_position,
        uint startbit);
uint larpix_uart_compute_parity(larpix_uart_packet* packet);
void larpix_uart_set_parity(larpix_uart_packet* packet);
uint larpix_uart_check_parity(larpix_uart_packet* packet);
void larpix_uart_set_packet_type(larpix_uart_packet* packet,
        larpix_packet_type type);
larpix_packet_type larpix_uart_get_packet_type(larpix_uart_packet* packet);
void larpix_uart_set_chipid(larpix_uart_packet* packet, uint chipid);
uint larpix_uart_get_chipid(larpix_uart_packet* packet);


#endif //ifndef LARPIX_H
