#include <stdio.h>
#include "larpix.h"

int main()
{
    larpix_connection _c;
    larpix_connection* c = &_c;

    larpix_default_connection(c);
    uint status = larpix_connect(c);
    if(status != 0)
    {
        printf("Could not connect (exit code %d)\n", status);
        return 1;
    }
    c->pin_io_directions = 0x03;
    status = larpix_configure_ftdi(c);
    if(status != 0)
    {
        printf("Could not configure (exit code %d)\n", status);
    }
    larpix_uart_packet p;
    larpix_uart_set_packet_type(&p, LARPIX_PACKET_CONFIG_WRITE);
    larpix_uart_set_chipid(&p, 12);
    larpix_uart_set_parity(&p);
    larpix_data data_array[10];
    for(uint i = 0; i < 10; ++i)
    {
        larpix_data* data = data_array + i;
        larpix_data_init_high(data);
        larpix_data_set_clk(data, 0);
        status = larpix_uart_to_data(&p, data, 1, 50 * i);
    }
    uint num_bytes_written = larpix_write_data(c, data_array, 10,
            LARPIX_BUFFER_SIZE);
    printf("Wrote %d bytes to FTDI chip\n", num_bytes_written);

    larpix_disconnect(c);
    return 0;
}
