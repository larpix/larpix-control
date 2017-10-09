#include "larpix.h"
#include "larpix_config_registers.h"

uint larpix_buffer_size()
{
    return LARPIX_BUFFER_SIZE;
}

uint larpix_uart_size()
{
    return LARPIX_UART_SIZE;
}

ulong larpix_bitstream_to_int(byte* bitstream, uint length)
{
    // Note: unsigned ints (uints) only hold 16 bits. We expect some of
    // the results here to be up to 24 bits (e.g. timestamp).
    ulong result = 0;
    for(uint i = 0; i < length; ++i)
    {
        if(!(bitstream[i] == 0))
        {
            ulong value_to_add = 1 << i;
            result += value_to_add;
        }
    }
    return result;
}

void larpix_int_to_bitstream(byte* bitstream, ulong input, uint length)
{
    for(uint i = 0; i < length; ++i)
    {
        ulong bit_to_test = 1 << i;
        if((input & bit_to_test) == 0)
        {
            bitstream[i] = 0;
        }
        else
        {
            bitstream[i] = 1;
        }
    }
    return;
}

void larpix_default_connection(larpix_connection* c)
{
    c->port_number = 0;
    c->clk_divisor = 0;
    c->pin_io_directions = 0x01;
    c->bit_mode = FT_BITMODE_SYNC_BITBANG;
    c->timeout = 10;
    c->usb_transfer_size = 64;
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

uint larpix_write_data(larpix_connection* c,
        larpix_data* data_array,
        uint num_writes,
        uint num_bytes_per_write)
{
    if(num_bytes_per_write > LARPIX_BUFFER_SIZE)
    {
        num_bytes_per_write = LARPIX_BUFFER_SIZE;
    }
    FT_STATUS status = FT_OK;
    FT_Purge(c->ft_handle, FT_PURGE_TX);
    byte output_buffer[LARPIX_BUFFER_SIZE];
    uint counter = 0;
    uint tot_num_bytes_written = 0;
    uint num_bytes_written = 0;
    while(status == FT_OK && counter < num_writes)
    {
        larpix_data* data = &(data_array[counter]);
        larpix_data_to_array(data, output_buffer, num_bytes_per_write);
        status = FT_Write(c->ft_handle,
                output_buffer,
                num_bytes_per_write,
                &num_bytes_written);
        tot_num_bytes_written += num_bytes_written;
        ++counter;
    }
    return tot_num_bytes_written;
}

uint larpix_read_data(larpix_connection* c,
        larpix_data* data_array,
        uint num_reads,
        uint num_bytes_per_read)
{
    if(num_bytes_per_read > LARPIX_BUFFER_SIZE)
    {
        num_bytes_per_read = LARPIX_BUFFER_SIZE;
    }
    FT_STATUS status = FT_OK;
    byte input_buffer[LARPIX_BUFFER_SIZE];
    uint counter = 0;
    uint tot_num_bytes_read = 0;
    uint num_bytes_read = 0;
    while(status == FT_OK && counter < num_reads)
    {
        larpix_data* data = &(data_array[counter]);
        status = FT_Read(c->ft_handle,
                input_buffer,
                num_bytes_per_read,
                &num_bytes_read);
        larpix_array_to_data(data, input_buffer, num_bytes_per_read);
        tot_num_bytes_read += num_bytes_read;
        ++counter;
    }
    return tot_num_bytes_read;
}
void larpix_write_read_data(larpix_connection* c,
        larpix_data* write_array,
        larpix_data* read_array,
        uint num_read_writes,
        uint num_bytes_per_write,
        uint num_bytes_per_read,
        uint* total_num_bytes_written,
        uint* total_num_bytes_read)
{
    if(num_bytes_per_read > LARPIX_BUFFER_SIZE)
    {
        num_bytes_per_read = LARPIX_BUFFER_SIZE;
    }
    if(num_bytes_per_write > LARPIX_BUFFER_SIZE)
    {
        num_bytes_per_write = LARPIX_BUFFER_SIZE;
    }
    FT_STATUS status = FT_OK;
    byte input_buffer[LARPIX_BUFFER_SIZE];
    byte output_buffer[LARPIX_BUFFER_SIZE];
    uint counter = 0;
    uint tot_num_bytes_read = 0;
    uint tot_num_bytes_written = 0;
    uint num_bytes_read = 0;
    uint num_bytes_written = 0;
    while(status == FT_OK && counter < num_read_writes)
    {
        larpix_data* input_data = &(read_array[counter]);
        larpix_data* output_data = &(write_array[counter]);
        larpix_array_to_data(output_data, output_buffer, num_bytes_per_write);
        status = FT_Write(c->ft_handle,
                output_buffer,
                num_bytes_per_write,
                &num_bytes_written);
        status = FT_Read(c->ft_handle,
                input_buffer,
                num_bytes_per_read,
                &num_bytes_read);
        larpix_array_to_data(input_data, input_buffer, num_bytes_per_read);
        tot_num_bytes_read += num_bytes_read;
        tot_num_bytes_written += num_bytes_written;
        ++counter;
    }
    *total_num_bytes_read = tot_num_bytes_read;
    *total_num_bytes_written = tot_num_bytes_written;
    return;
}

void larpix_data_init_high(larpix_data* data)
{
    for(uint bit_position = 0; bit_position < 8; ++bit_position)
    {
        for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
        {
            data->bits[bit_position][i] = 1;
        }
    }
    return;
}

void larpix_data_init_low(larpix_data* data)
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

void larpix_data_set_clk(larpix_data* data, uint bit_position)
{
    byte clk_pattern[LARPIX_BUFFER_SIZE];
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        clk_pattern[i] = i % 2;
    }
    larpix_data_set_bitstream(data, clk_pattern, bit_position, LARPIX_BUFFER_SIZE);
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

uint larpix_uart_to_data(larpix_uart_packet* packet, larpix_data* data,
        uint bit_position,
        uint startbit)
{
    uint size_in_buffer = (LARPIX_UART_SIZE + 2) * LARPIX_BITS_PER_BAUD;
    if(startbit + size_in_buffer > LARPIX_BUFFER_SIZE)
    {
        return 1;
    }
    byte* bit_channel = data->bits[bit_position];
    // UART spec: 0th bit is 0, last bit is 1
    for(uint j = 0; j < LARPIX_BITS_PER_BAUD; ++j)
    {
        bit_channel[startbit + j] = 0;
        bit_channel[startbit + size_in_buffer - j - 1] = 1;
    }
    uint BPB = LARPIX_BITS_PER_BAUD;
    for(uint i = 0; i < LARPIX_UART_SIZE; ++i)
    {
        for(uint j = 0; j < LARPIX_BITS_PER_BAUD; ++j)
        {
            uint write_position = startbit + (i+1)*BPB + j;
            bit_channel[write_position] = packet->data[i];
        }
    }
    return 0;
}

uint larpix_data_to_uart(larpix_uart_packet* packet, larpix_data* data,
        uint bit_position,
        uint startbit)
{
    if(startbit + LARPIX_UART_SIZE + 2 > LARPIX_BUFFER_SIZE)
    {
        return 1;
    }
    byte* bit_channel = data->bits[bit_position];
    for(uint i = 0; i < LARPIX_UART_SIZE; ++i)
    {
        uint read_position = startbit + i + 1;
         packet->data[i] = bit_channel[read_position];
    }
    return 0;
}

void larpix_uart_set_packet_type(larpix_uart_packet* packet,
        larpix_packet_type type)
{
    uint start = LARPIX_UART_PTYPE_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_PTYPE_HIGH - start;
    larpix_int_to_bitstream(startbit, (ulong) type, length);
    return;
}

larpix_packet_type larpix_uart_get_packet_type(larpix_uart_packet* packet)
{
    uint start = LARPIX_UART_PTYPE_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_PTYPE_HIGH - start;
    ulong value = larpix_bitstream_to_int(startbit, length);
    return (larpix_packet_type) value;
}

void larpix_uart_set_chipid(larpix_uart_packet* packet, uint chipid)
{
    uint start = LARPIX_UART_CHIPID_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_CHIPID_HIGH - start;
    larpix_int_to_bitstream(startbit, (ulong) chipid, length);
    return;
}

uint larpix_uart_get_chipid(larpix_uart_packet* packet)
{
    uint start = LARPIX_UART_CHIPID_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_CHIPID_HIGH - start;
    ulong value = larpix_bitstream_to_int(startbit, length);
    return (uint) value;
}

byte larpix_uart_compute_parity(larpix_uart_packet* packet)
{
    uint number_of_ones = 0;
    for(uint i = 0; i < LARPIX_UART_PARITY; ++i)
    {
        if(packet->data[i] == 1)
        {
            ++number_of_ones;
        }
    }
    byte parity = 1 - (byte)(number_of_ones % 2);
    return parity;
}

void larpix_uart_set_parity(larpix_uart_packet* packet)
{
    byte parity = larpix_uart_compute_parity(packet);
    packet->data[LARPIX_UART_PARITY] = parity;
    return;
}

void larpix_uart_force_set_parity(larpix_uart_packet* packet, byte parity)
{
    if(parity == 0)
    {
        packet->data[LARPIX_UART_PARITY] = 0;
    }
    else
    {
        packet->data[LARPIX_UART_PARITY] = 1;
    }
    return;
}

byte larpix_uart_get_parity(larpix_uart_packet* packet)
{
    return packet->data[LARPIX_UART_PARITY];
}

uint larpix_uart_check_parity(larpix_uart_packet* packet)
{
    byte computed_parity = larpix_uart_compute_parity(packet);
    byte received_parity = packet->data[LARPIX_UART_PARITY];
    if(computed_parity == received_parity)
    {
        return 0;
    }
    else
    {
        return 1;
    }
}

void larpix_uart_set_channelid(larpix_uart_packet* packet, uint channelid)
{
    uint start = LARPIX_UART_CHANNELID_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_CHANNELID_HIGH - start;
    larpix_int_to_bitstream(startbit, (ulong) channelid, length);
    return;
}

uint larpix_uart_get_channelid(larpix_uart_packet* packet)
{
    uint start = LARPIX_UART_CHANNELID_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_CHANNELID_HIGH - start;
    ulong value = larpix_bitstream_to_int(startbit, length);
    return (uint) value;
}

void larpix_uart_set_timestamp(larpix_uart_packet* packet, ulong timestamp)
{
    uint start = LARPIX_UART_TIMESTAMP_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_TIMESTAMP_HIGH - start;
    larpix_int_to_bitstream(startbit, timestamp, length);
    return;
}

ulong larpix_uart_get_timestamp(larpix_uart_packet* packet)
{
    uint start = LARPIX_UART_TIMESTAMP_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_TIMESTAMP_HIGH - start;
    ulong value = larpix_bitstream_to_int(startbit, length);
    return value;
}

void larpix_uart_set_dataword(larpix_uart_packet* packet, uint dataword)
{
    uint start = LARPIX_UART_DATAWORD_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_DATAWORD_HIGH - start;
    larpix_int_to_bitstream(startbit, (ulong) dataword, length);
    return;
}

uint larpix_uart_get_dataword(larpix_uart_packet* packet)
{
    uint start = LARPIX_UART_DATAWORD_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_DATAWORD_HIGH - start;
    ulong value = larpix_bitstream_to_int(startbit, length);
    return (uint) value;
}

void larpix_uart_set_fifohalfflag(larpix_uart_packet* packet, byte fifohalfflag)
{
    if(fifohalfflag == 0)
    {
        packet->data[LARPIX_UART_FIFO_HALF] = fifohalfflag;
    }
    else
    {
        packet->data[LARPIX_UART_FIFO_HALF] = 1;
    }
    return;
}

byte larpix_uart_get_fifohalfflag(larpix_uart_packet* packet)
{
    return packet->data[LARPIX_UART_FIFO_HALF];
}

void larpix_uart_set_fifofullflag(larpix_uart_packet* packet, byte fifofullflag)
{
    if(fifofullflag == 0)
    {
        packet->data[LARPIX_UART_FIFO_FULL] = 0;
    }
    else
    {
        packet->data[LARPIX_UART_FIFO_FULL] = 1;
    }
    return;
}

byte larpix_uart_get_fifofullflag(larpix_uart_packet* packet)
{
    return packet->data[LARPIX_UART_FIFO_FULL];
}

uint larpix_uart_get_test_counter(larpix_uart_packet* packet)
{
    uint start = LARPIX_UART_TEST_BITS_11_0_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_TEST_BITS_11_0_HIGH - start;
    ulong value = larpix_bitstream_to_int(startbit, length);

    uint start2 = LARPIX_UART_TEST_BITS_15_12_LOW;
    byte* startbit2 = &(packet->data[start2]);
    uint length2 = 1 + LARPIX_UART_TEST_BITS_15_12_HIGH - start2;
    ulong value2 = larpix_bitstream_to_int(startbit2, length2);
    value2 = value2 << length;
    return (uint) (value + value2);
}

void larpix_uart_set_register(larpix_uart_packet* packet, uint address)
{
    uint start = LARPIX_UART_REGISTER_ADDRESS_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_REGISTER_ADDRESS_HIGH - start;
    larpix_int_to_bitstream(startbit, (ulong) address, length);
    return;
}

uint larpix_uart_get_register(larpix_uart_packet* packet)
{
    uint start = LARPIX_UART_REGISTER_ADDRESS_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_REGISTER_ADDRESS_HIGH - start;
    ulong value = larpix_bitstream_to_int(startbit, length);
    return (uint) value;
}

void larpix_uart_set_register_data(larpix_uart_packet* packet, uint value)
{
    uint start = LARPIX_UART_REGISTER_DATA_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_REGISTER_DATA_HIGH - start;
    larpix_int_to_bitstream(startbit, (ulong) value, length);
    return;
}

uint larpix_uart_get_register_data(larpix_uart_packet* packet)
{
    uint start = LARPIX_UART_REGISTER_DATA_LOW;
    byte* startbit = &(packet->data[start]);
    uint length = 1 + LARPIX_UART_REGISTER_DATA_HIGH - start;
    ulong value = larpix_bitstream_to_int(startbit, length);
    return (uint) value;
}

void larpix_config_init_defaults(larpix_configuration* config)
{
    byte default_pixel_trim_threshold = 0x10;
    for(uint i = 0; i < LARPIX_NUM_CHANNELS; ++i)
    {
        config->pixel_trim_thresholds[i] = default_pixel_trim_threshold;
    }
    config->global_threshold = 0x10;
    config->csa_gain = 0x1;
    config->csa_bypass = 0x0;
    config->internal_bypass = 0x1;
    byte default_bypass_select = 0x0;
    byte default_monitor_select = 0x1;
    byte default_testpulse_enable = 0x0;
    for(uint i = 0; i < LARPIX_NUM_CHANNELS; ++i)
    {
        config->csa_bypass_select[i] = default_bypass_select;
        config->csa_monitor_select[i] = default_monitor_select;
        config->csa_testpulse_enable[i] = default_testpulse_enable;
    }
    config->csa_testpulse_dac_amplitude = 0x0;
    config->test_mode = 0x0;
    config->cross_trigger_mode = 0x0;
    config->periodic_reset = 0x0;
    config->fifo_diagnostic = 0x0;
    config->sample_cycles = 0x1;
    config->test_burst_length[0] = 0x00;
    config->test_burst_length[1] = 0xFF;
    config->adc_burst_length = 0;
    byte default_channel_mask = 0x0;
    byte default_external_trigger_mask = 0x1;
    for(uint i = 0; i < LARPIX_NUM_CHANNELS; ++i)
    {
        config->channel_mask[i] = default_channel_mask;
        config->external_trigger_mask[i] = default_external_trigger_mask;
    }
    config->reset_cycles[0] = 0x00;
    config->reset_cycles[1] = 0x10;
    config->reset_cycles[2] = 0x00;
    return;
}

void larpix_config_write_all(larpix_configuration* config,
        larpix_uart_packet packets[LARPIX_NUM_CONFIG_REGISTERS])
{
    // This is a pain
    larpix_uart_packet* packet = packets;
    for(uint i = 0; i < LARPIX_NUM_CHANNELS; ++i)
    {
        larpix_config_write_pixel_trim_threshold(config, packet, i);
        ++packet;
    }
    larpix_config_write_global_threshold(config, packet);
    ++packet;
    larpix_config_write_csa_gain_and_bypasses(config, packet);
    ++packet;
    for(uint i = 0; i < 4; ++i)
    {
        larpix_config_write_csa_bypass_select(config, packet, i);
        ++packet;
    }
    for(uint i = 0; i < 4; ++i)
    {
        larpix_config_write_csa_monitor_select(config, packet, i);
        ++packet;
    }
    for(uint i = 0; i < 4; ++i)
    {
        larpix_config_write_csa_testpulse_enable(config, packet, i);
        ++packet;
    }
    larpix_config_write_csa_testpulse_dac_amplitude(config, packet);
    ++packet;
    larpix_config_write_test_mode_xtrig_reset_diag(config, packet);
    ++packet;
    larpix_config_write_sample_cycles(config, packet);
    ++packet;
    for(uint i = 0; i < 2; ++i)
    {
        larpix_config_write_test_burst_length(config, packet, i);
        ++packet;
    }
    larpix_config_write_adc_burst_length(config, packet);
    ++packet;
    for(uint i = 0; i < 4; ++i)
    {
        larpix_config_write_channel_mask(config, packet, i);
        ++packet;
    }
    for(uint i = 0; i < 4; ++i)
    {
        larpix_config_write_external_trigger_mask(config, packet, i);
        ++packet;
    }
    for(uint i = 0; i < 3; ++i)
    {
        larpix_config_write_reset_cycles(config, packet, i);
        ++packet;
    }
    return;
}
uint larpix_config_read_all(larpix_configuration* config,
        larpix_uart_packet packets[LARPIX_NUM_CONFIG_REGISTERS])
{
    // This is a pain
    uint status = 0;
    larpix_uart_packet* packet = packets;
    for(uint i = 0; i < LARPIX_NUM_CHANNELS; ++i)
    {
        status += larpix_config_read_pixel_trim_threshold(config, packet, i);
        ++packet;
    }
    status += larpix_config_read_global_threshold(config, packet);
    ++packet;
    status += larpix_config_read_csa_gain_and_bypasses(config, packet);
    ++packet;
    for(uint i = 0; i < 4; ++i)
    {
	status += larpix_config_read_csa_bypass_select(config, packet);
	++packet;
    }
    for(uint i = 0; i < 4; ++i)
    {
        status += larpix_config_read_csa_monitor_select(config, packet);
        ++packet;
    }
    for(uint i = 0; i < 4; ++i)
    {
        status += larpix_config_read_csa_testpulse_enable(config, packet);
        ++packet;
    }
    status += larpix_config_read_csa_testpulse_dac_amplitude(config, packet);
    ++packet;
    status += larpix_config_read_test_mode_xtrig_reset_diag(config, packet);
    ++packet;
    status += larpix_config_read_sample_cycles(config, packet);
    ++packet;
    for(uint i = 0; i < 2; ++i)
    {
        status += larpix_config_read_test_burst_length(config, packet);
        ++packet;
    }
    status += larpix_config_read_adc_burst_length(config, packet);
    ++packet;
    for(uint i = 0; i < 4; ++i)
    {
        status += larpix_config_read_channel_mask(config, packet);
        ++packet;
    }
    for(uint i = 0; i < 4; ++i)
    {
        status += larpix_config_read_external_trigger_mask(config, packet);
        ++packet;
    }
    for(uint i = 0; i < 3; ++i)
    {
        status += larpix_config_read_reset_cycles(config, packet);
        ++packet;
    }
    return status;
}

void larpix_config_write_pixel_trim_threshold(larpix_configuration* config,
        larpix_uart_packet* packet, uint channelid)
{
    byte value = config->pixel_trim_thresholds[channelid];
    byte address = LARPIX_REG_PIXEL_TRIM_THRESHOLD_LOW + channelid;
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
    return;
}

uint larpix_config_read_pixel_trim_threshold(larpix_configuration* config,
        larpix_uart_packet* packet, uint channelid)
{
    byte address = larpix_uart_get_register(packet);
    if(channelid != address - LARPIX_REG_PIXEL_TRIM_THRESHOLD_LOW)
    {
        return 1;
    }
    else
    {
        byte value = larpix_uart_get_register_data(packet);
        config->pixel_trim_thresholds[channelid] = value;
        return 0;
    }
}

void larpix_config_write_global_threshold(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte value = config->global_threshold;
    byte address = LARPIX_REG_GLOBAL_THRESHOLD;
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
    return;
}

uint larpix_config_read_global_threshold(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address != LARPIX_REG_GLOBAL_THRESHOLD)
    {
        return 1;
    }
    else
    {
        byte value = larpix_uart_get_register_data(packet);
        config->global_threshold = value;
        return 0;
    }
}

void larpix_config_write_csa_gain_and_bypasses(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte value;
    value = config->csa_gain;
    value += config->csa_bypass * 2;
    value += config->internal_bypass * 4;
    byte address = LARPIX_REG_CSA_GAIN_AND_BYPASSES;
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
    return;
}

uint larpix_config_read_csa_gain_and_bypasses(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address != LARPIX_REG_CSA_GAIN_AND_BYPASSES)
      {
	return 1;
      }
    else
      {
	byte value = larpix_uart_get_register_data(packet);
	config->csa_gain = (value & 1);
	config->csa_bypass = (value >> 1) & 1;
	config->internal_bypass = (value >> 2) & 1;
	return 0;
      }
}

void larpix_config_write_csa_bypass_select(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk)
{
    byte value = 0;
    byte address = LARPIX_REG_CSA_BYPASS_SELECT_LOW + channel_chunk;
    for ( uint i = 0; i < 8; i++ ) 
      {
	uint channel = channel_chunk * 8 + i;
	byte channel_value = config->csa_bypass_select[channel];
	value = value | (channel_value << i);
      }
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
    return;
}

uint larpix_config_read_csa_bypass_select(larpix_configuration* config,
					  larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address < LARPIX_REG_CSA_BYPASS_SELECT_LOW || address > LARPIX_REG_CSA_BYPASS_SELECT_HIGH )
      {
	return 1;
      }
    else
      {
	byte value = larpix_uart_get_register_data(packet);
	for ( uint i = 0; i < 8; i++ )
	  {
	    uint channel = (address - LARPIX_REG_CSA_BYPASS_SELECT_LOW) * 8 + i;
	    byte channel_value = (value >> i) & 1;
	    config->csa_bypass_select[channel] = channel_value;
	  }
	return 0;
      }
}

void larpix_config_write_csa_monitor_select(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk)
{
    byte value = 0;
    byte address = LARPIX_REG_CSA_MONITOR_SELECT_LOW + channel_chunk;
    for ( uint i = 0; i < 8; i++ ) 
      {
	uint channel = channel_chunk * 8 + i;
	byte channel_value = config->csa_monitor_select[channel];
	value = value | (channel_value << i);
      }
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
    return;
}

uint larpix_config_read_csa_monitor_select(larpix_configuration* config,
					   larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address < LARPIX_REG_CSA_MONITOR_SELECT_LOW || address > LARPIX_REG_CSA_MONITOR_SELECT_HIGH )
      {
	return 1;
      }
    else
      {
	byte value = larpix_uart_get_register_data(packet);
	for ( uint i = 0; i < 8; i++ )
	  {
	    uint channel = (address - LARPIX_REG_CSA_MONITOR_SELECT_LOW) * 8 + i;
	    byte channel_value = (value >> i) & 1;
	    config->csa_monitor_select[channel] = channel_value;
	  }
	return 0;
      }
}

void larpix_config_write_csa_testpulse_enable(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk)
{
    byte value = 0;
    byte address = LARPIX_REG_CSA_TESTPULSE_ENABLE_LOW + channel_chunk;
    for ( uint i = 0; i < 8; i++ ) 
      {
	uint channel = channel_chunk * 8 + i;
	byte channel_value = config->csa_testpulse_enable[channel];
	value = value | (channel_value << i);
      }
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
    return;
}

uint larpix_config_read_csa_testpulse_enable(larpix_configuration* config,
					     larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address < LARPIX_REG_CSA_TESTPULSE_ENABLE_LOW || address > LARPIX_REG_CSA_TESTPULSE_ENABLE_HIGH )
      {
	return 1;
      }
    else
      {
	byte value = larpix_uart_get_register_data(packet);
	for ( uint i = 0; i < 8; i++ )
	  {
	    uint channel = (address - LARPIX_REG_CSA_TESTPULSE_ENABLE_LOW) * 8 + i;
	    byte channel_value = (value >> i) & 1;
	    config->csa_testpulse_enable[channel] = channel_value;
	  }
	return 0;
      }
}

void larpix_config_write_csa_testpulse_dac_amplitude(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte value = config->csa_testpulse_dac_amplitude;
    byte address = LARPIX_REG_CSA_TESTPULSE_DAC_AMPLITUDE;
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
    return;
}

uint larpix_config_read_csa_testpulse_dac_amplitude(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address != LARPIX_REG_CSA_TESTPULSE_DAC_AMPLITUDE)
    {
      return 1;
    }
  else
    {
      byte value = larpix_uart_get_register_data(packet);
      config->csa_testpulse_dac_amplitude = value;
      return 0;
    }

}

void larpix_config_write_test_mode_xtrig_reset_diag(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte value = 0;
    byte address = LARPIX_REG_TEST_MODE_XTRIG_RESET_DIAG;
    value = value | config->test_mode; // bits [1:0]
    value = value | (config->cross_trigger_mode << 2); // bit [2]
    value = value | (config->periodic_reset << 3); // bit [3]
    value = value | (config->fifo_diagnostic << 4); // bit [4]
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
}

uint larpix_config_read_test_mode_xtrig_reset_diag(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address != LARPIX_REG_TEST_MODE_XTRIG_RESET_DIAG)
    {
      return 1;
    }
  else
    {
      byte value = larpix_uart_get_register_data(packet);
      config->test_mode = (value & 3); // bits [1:0]
      config->cross_trigger_mode = (value >> 2) & 1; // bit [2]
      config->periodic_reset = (value >> 3) & 1; // bit [3]
      config->fifo_diagnostic = (value >> 4) & 1; // bit [4]
      return 0;
    }
}

void larpix_config_write_sample_cycles(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte value = config->sample_cycles;
    byte address = LARPIX_REG_SAMPLE_CYCLES;
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
}

uint larpix_config_read_sample_cycles(larpix_configuration* config,
        larpix_uart_packet* packet)
{
  byte address = larpix_uart_get_register(packet);
  if(address != LARPIX_REG_SAMPLE_CYCLES)
    {
      return 1;
    }
  else
    {
      byte value = larpix_uart_get_register_data(packet);
      config->sample_cycles = value;
      return 0;
    }
}

void larpix_config_write_test_burst_length(larpix_configuration* config,
        larpix_uart_packet* packet, uint value_chunk)
{
    byte value = config->test_burst_length[value_chunk];
    byte address = LARPIX_REG_TEST_BURST_LENGTH_LOW + value_chunk;
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
}

uint larpix_config_read_test_burst_length(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address < LARPIX_REG_TEST_BURST_LENGTH_LOW || address > LARPIX_REG_TEST_BURST_LENGTH_HIGH)
      {
	return 1;
      }
    else
      {
	byte value = larpix_uart_get_register_data(packet);
	uint value_chunk = address - LARPIX_REG_TEST_BURST_LENGTH_LOW;
	config->test_burst_length[value_chunk] = value;
	return 0;
      }
}

void larpix_config_write_adc_burst_length(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte value = config->adc_burst_length;
    byte address = LARPIX_REG_ADC_BURST_LENGTH;
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
}

uint larpix_config_read_adc_burst_length(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address != LARPIX_REG_ADC_BURST_LENGTH)
      {
	return 1;
      }
    else
      {
	byte value = larpix_uart_get_register_data(packet);
	config->adc_burst_length = value;
	return 0;
      }    
}

void larpix_config_write_channel_mask(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk)
{
      byte value = 0;
      byte address = LARPIX_REG_CHANNEL_MASK_LOW + channel_chunk;
      for ( uint i = 0; i < 8; i++ ) 
	{
	  uint channel = channel_chunk * 8 + i;
	  byte channel_value = config->channel_mask[channel];
	  value = value | (channel_value << i);
	}
      larpix_uart_set_register(packet, address);
      larpix_uart_set_register_data(packet, value);
      return;
}

uint larpix_config_read_channel_mask(larpix_configuration* config,
				     larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address < LARPIX_REG_CHANNEL_MASK_LOW || address > LARPIX_REG_CHANNEL_MASK_HIGH)
      {
	return 1;
      }
    else
      {
	byte value = larpix_uart_get_register_data(packet);
	for ( uint i = 0; i < 8; i++ )
	  {
	    uint channel = (address - LARPIX_REG_CHANNEL_MASK_LOW) * 8 + i;
	    byte channel_value = (value >> i) & 1;
	    config->channel_mask[channel] = channel_value;
	  }
	return 0;
      }
}

void larpix_config_write_external_trigger_mask(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk)
{
      byte value = 0;
      byte address = LARPIX_REG_EXTERNAL_TRIGGER_MASK_LOW + channel_chunk;
      for ( uint i = 0; i < 8; i++ ) 
	{
	  uint channel = channel_chunk * 8 + i;
	  byte channel_value = config->external_trigger_mask[channel];
	  value = value | (channel_value << i);
	}
      larpix_uart_set_register(packet, address);
      larpix_uart_set_register_data(packet, value);
      return;
}

uint larpix_config_read_external_trigger_mask(larpix_configuration* config,
					      larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address < LARPIX_REG_EXTERNAL_TRIGGER_MASK_LOW || address > LARPIX_REG_EXTERNAL_TRIGGER_MASK_HIGH)
      {
	return 1;
      }
    else
      {
	byte value = larpix_uart_get_register_data(packet);
	for ( uint i = 0; i < 8; i++ )
	  {
	    uint channel = (address - LARPIX_REG_EXTERNAL_TRIGGER_MASK_LOW) * 8 + i;
	    byte channel_value = (value >> i) & 1;
	    config->external_trigger_mask[channel] = channel_value;
	  }
	return 0;
      }
}

void larpix_config_write_reset_cycles(larpix_configuration* config,
        larpix_uart_packet* packet, uint value_chunk)
{
    byte value = config->reset_cycles[value_chunk];
    byte address = LARPIX_REG_RESET_CYCLES_LOW + value_chunk;
    larpix_uart_set_register(packet, address);
    larpix_uart_set_register_data(packet, value);
}

uint larpix_config_read_reset_cycles(larpix_configuration* config,
        larpix_uart_packet* packet)
{
    byte address = larpix_uart_get_register(packet);
    if(address < LARPIX_REG_RESET_CYCLES_LOW || address > LARPIX_REG_RESET_CYCLES_HIGH)
      {
	return 1;
      }
    else
      {
	byte value = larpix_uart_get_register_data(packet);
	uint value_chunk = address - LARPIX_REG_RESET_CYCLES_LOW;
	config->test_burst_length[value_chunk] = value;
	return 0;
      }
}
