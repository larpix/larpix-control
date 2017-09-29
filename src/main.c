#include <stdio.h>
#include "larpix.h"

int main()
{
    larpix_connection _c;
    larpix_connection* c = &_c;

    larpix_default_connection(c);
    int status = larpix_connect(c);
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
    byte ch1[LARPIX_BUFFER_SIZE];
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        ch1[i] = 0;
    }
    ch1[1] = 1;
    ch1[10] = 1;
    ch1[100] = 1;
    ch1[1000] = 1;
    larpix_data_set_bitstream(&(c->output_data), ch1, 1, LARPIX_BUFFER_SIZE);
    uint num_bytes_written = larpix_write_data_loop(c, 10);
    printf("Wrote %d bytes to FTDI chip\n", num_bytes_written);

    larpix_disconnect(c);
    return 0;
}
