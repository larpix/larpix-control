#include "larpix.h"

void larpix_default_connection(larpix_connection* c)
{
    c->port_number = 0;
    c->clk_divisor = 0;
    c->pin_io_directions = 0x01;
    c->bit_mode = FT_BITMODE_SYNC_BITBANG;
    c->timeout = 10;
    c->usb_transfer_size = 64;
    for(uint i = 0; i < 1024; ++i)
    {
        c->output_buffer[i] = 0;
    }
    return;
}
int larpix_connect(larpix_connection* c)
{
    FT_STATUS status = FT_Open(c->port_number, &(c->ft_handle));
    return (int) status;
}

int larpix_disconnect(larpix_connection* c)
{
    FT_STATUS status = FT_Close(&(c->ft_handle));
    return (int) status;
}

int larpix_configure_ftdi(larpix_connection* c)
{
    FT_HANDLE* handle = &(c->ft_handle);
    FT_STATUS status = FT_OK;
    status |= FT_SetBitMode(handle,
            c->pin_io_directions,
            c->bit_mode);
    status |= FT_SetDivisor(handle, c->clk_divisor);
    status |= FT_SetTimeouts(handle, c->timeout, c->timeout);
    status |= FT_SetUSBParameters(handle,
            c->usb_transfer_size,
            c->usb_transfer_size);
    return (int) status;
}

uint larpix_write_zeros_loop(larpix_connection* c, uint num_loops)
{
    FT_HANDLE* handle = &(c->ft_handle);

    FT_STATUS status = FT_OK;
    uint counter = 0;
    uint tot_num_bytes_written = 0;
    uint num_bytes_written = 0;
    while(status == FT_OK && counter < num_loops)
    {
        status = FT_Write(handle,
                c->output_buffer,
                LARPIX_BUFFER_SIZE,
                &num_bytes_written);
        tot_num_bytes_written += num_bytes_written;
        ++counter;
    }
    return tot_num_bytes_written;
}
