#include "larpix.h"

void larpix_default_connection(larpix_connection* c)
{
    c->port_number = 0;
    c->clk_divisor = 0;
    c->pin_io_directions = 0x01;
    c->bit_mode = FT_BITMODE_SYNC_BITBANG;
    c->timeout = 10;
    c->usb_transfer_size = 64;
    byte clk_pattern[LARPIX_BUFFER_SIZE];
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        clk_pattern[i] = i % 2;
    }
    larpix_data* data = &(c->output_data);
    larpix_data_init(data);
    larpix_data_set_bitstream(data, clk_pattern, 0, LARPIX_BUFFER_SIZE);
    return;
}
int larpix_connect(larpix_connection* c)
{
    FT_STATUS status = FT_Open(c->port_number, &(c->ft_handle));
    return (int) status;
}

int larpix_disconnect(larpix_connection* c)
{
    FT_STATUS status = FT_Close(c->ft_handle);
    return (int) status;
}

int larpix_configure_ftdi(larpix_connection* c)
{
    FT_STATUS status = FT_OK;
    status |= FT_SetBitMode(c->ft_handle,
            c->pin_io_directions,
            c->bit_mode);
    status |= FT_SetDivisor(c->ft_handle, c->clk_divisor);
    status |= FT_SetTimeouts(c->ft_handle, c->timeout, c->timeout);
    status |= FT_SetUSBParameters(c->ft_handle,
            c->usb_transfer_size,
            c->usb_transfer_size);
    return (int) status;
}

uint larpix_write_data_loop(larpix_connection* c, uint num_loops)
{

    FT_STATUS status = FT_OK;
    FT_Purge(c->ft_handle, FT_PURGE_RX | FT_PURGE_TX);
    byte output_buffer[LARPIX_BUFFER_SIZE];
    larpix_data_to_array(&(c->output_data), output_buffer, LARPIX_BUFFER_SIZE);
    uint counter = 0;
    uint tot_num_bytes_written = 0;
    uint num_bytes_written = 0;
    while(status == FT_OK && counter < num_loops)
    {
        status = FT_Write(c->ft_handle,
                output_buffer,
                LARPIX_BUFFER_SIZE,
                &num_bytes_written);
        tot_num_bytes_written += num_bytes_written;
        ++counter;
    }
    return tot_num_bytes_written;
}

void larpix_data_init(larpix_data* data)
{
    for(uint bit_position = 0; bit_position < 8; ++bit_position)
    {
        for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
        {
            data->bits[bit_position][i] = 0;
        }
    }
    return;
}

void larpix_data_to_array(larpix_data* data, byte* array, uint nbytes)
{
    if(nbytes > LARPIX_BUFFER_SIZE)
    {
        nbytes = LARPIX_BUFFER_SIZE;
    }
    for(uint i = 0; i < nbytes; ++i)
    {
        array[i] = 0;
        for(uint bit_position = 0; bit_position < 8; ++bit_position)
        {
            byte binary_form = 1 << bit_position;
            if(data->bits[bit_position][i] != 0)
            {
                array[i] += binary_form;
            }
        }
    }
    return;
}

void larpix_array_to_data(larpix_data* data, byte* array, uint nbytes)
{
    if(nbytes > LARPIX_BUFFER_SIZE)
    {
        nbytes = LARPIX_BUFFER_SIZE;
    }
    for(uint i = 0; i < nbytes; ++i)
    {
        for(uint bit_position = 0; bit_position < 8; ++bit_position)
        {
            // Check if the desired bit is set
            byte binary_form = 1 << bit_position;
            if((binary_form & array[i]) != 0)
            {
                data->bits[bit_position][i] = 1;
            }
            else
            {
                data->bits[bit_position][i] = 0;
            }
        }
    }
    return;
}

void larpix_data_set_bitstream(larpix_data* data,
        byte* array,
        uint bit_position,
        uint nbytes)
{
    if(nbytes > LARPIX_BUFFER_SIZE)
    {
        nbytes = LARPIX_BUFFER_SIZE;
    }
    for(uint i = 0; i < nbytes; ++i)
    {
        if(array[i] == 0)
        {
            data->bits[bit_position][i] = 0;
        }
        else
        {
            data->bits[bit_position][i] = 1;
        }
    }
    return;
}

void larpix_data_get_bitstream(larpix_data* data,
        byte* array,
        uint bit_position,
        uint nbytes)
{
    if(nbytes > LARPIX_BUFFER_SIZE)
    {
        nbytes = LARPIX_BUFFER_SIZE;
    }
    for(uint i = 0; i < nbytes; ++i)
    {
        if(data->bits[bit_position][i] == 0)
        {
            array[i] = 0;
        }
        else
        {
            array[i] = 1;
        }
    }
    return;
}
