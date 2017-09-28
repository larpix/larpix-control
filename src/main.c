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
    status = larpix_configure_ftdi(c);
    if(status != 0)
    {
        printf("Could not configure (exit code %d)\n", status);
    }
    uint num_bytes_written = larpix_write_clock_loop(c, 10);
    printf("Wrote %d bytes to FTDI chip\n", num_bytes_written);

    larpix_disconnect(c);
    return 0;
}
