#ifndef LARPIX_H
#define LARPIX_H

#include <ftd2xx/ftd2xx.h>

typedef unsigned int uint;
typedef unsigned long ulong;
typedef unsigned char byte;

#define LARPIX_BUFFER_SIZE 1024
#define LARPIX_UART_SIZE 54
#define LARPIX_BITS_PER_BAUD 4
#define LARPIX_NUM_CHANNELS 32
#define LARPIX_NUM_CONFIG_REGISTERS 63

// UART bits for all packet types
#define LARPIX_UART_PTYPE_LOW 0
#define LARPIX_UART_PTYPE_HIGH 1
#define LARPIX_UART_CHIPID_LOW 2
#define LARPIX_UART_CHIPID_HIGH 9
#define LARPIX_UART_PARITY 53

// UART bits for data packets
#define LARPIX_UART_CHANNELID_LOW 10
#define LARPIX_UART_CHANNELID_HIGH 16
#define LARPIX_UART_TIMESTAMP_LOW 17
#define LARPIX_UART_TIMESTAMP_HIGH 40
#define LARPIX_UART_DATAWORD_LOW 41
#define LARPIX_UART_DATAWORD_HIGH 50
#define LARPIX_UART_FIFO_HALF 51
#define LARPIX_UART_FIFO_FULL 52

// UART bits for configuration packets
#define LARPIX_UART_REGISTER_ADDRESS_LOW 10
#define LARPIX_UART_REGISTER_ADDRESS_HIGH 17
#define LARPIX_UART_REGISTER_DATA_LOW 18
#define LARPIX_UART_REGISTER_DATA_HIGH 25
#define LARPIX_UART_CONFIG_UNUSED_LOW 26
#define LARPIX_UART_CONFIG_UNUSED_HIGH 52

// UART bits for UART test packets
#define LARPIX_UART_NUM_TEST_BITS 16
#define LARPIX_UART_TEST_BITS_11_0_LOW 41
#define LARPIX_UART_TEST_BITS_11_0_HIGH 52
#define LARPIX_UART_TEST_BITS_15_12_LOW 10
#define LARPIX_UART_TEST_BITS_15_12_HIGH 13

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

typedef struct larpix_configuration
{
    byte pixel_trim_thresholds[LARPIX_NUM_CHANNELS];
    byte global_threshold;
    byte csa_gain;
    byte csa_bypass;
    byte internal_bypass;
    byte csa_bypass_select[LARPIX_NUM_CHANNELS];
    byte csa_monitor_select[LARPIX_NUM_CHANNELS];
    byte csa_testpulse_enable[LARPIX_NUM_CHANNELS];
    byte csa_testpulse_dac_amplitude;
    byte test_mode;
    byte cross_trigger_mode;
    byte periodic_reset;
    byte fifo_diagnostic;
    byte sample_cycles;
    byte test_burst_length[2];
    byte adc_burst_length;
    byte channel_mask[LARPIX_NUM_CHANNELS];
    byte external_trigger_mask[LARPIX_NUM_CHANNELS];
    byte reset_cycles[3];
} larpix_configuration;

typedef enum larpix_packet_type
{
    LARPIX_PACKET_DATA,
    LARPIX_PACKET_TEST,
    LARPIX_PACKET_CONFIG_WRITE,
    LARPIX_PACKET_CONFIG_READ
} larpix_packet_type;

uint larpix_buffer_size();
uint larpix_uart_size();
ulong larpix_bitstream_to_int(byte* bitstream, uint length);
void larpix_int_to_bitstream(byte* bitstream, ulong input, uint length);
void larpix_default_connection(larpix_connection* c);
int larpix_connect(larpix_connection* c);
int larpix_disconnect(larpix_connection* c);
int larpix_configure_ftdi(larpix_connection* c);
uint larpix_write_data(larpix_connection* c,
        larpix_data* data_array,
        uint num_writes,
        uint num_bytes_per_write);
uint larpix_read_data(larpix_connection* c,
        larpix_data* data_array,
        uint num_reads,
        uint num_bytes_per_read);
void larpix_write_read_data(larpix_connection* c,
        larpix_data* write_array,
        larpix_data* read_array,
        uint num_read_writes,
        uint num_bytes_per_write,
        uint num_bytes_per_read,
        uint* total_bytes_written,
        uint* total_bytes_read);

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
void larpix_uart_str(larpix_uart_packet* packet, char* buffer, uint length);
void larpix_uart_init_zeros(larpix_uart_packet* packet);

// UART access for all packet types
void larpix_uart_set_packet_type(larpix_uart_packet* packet,
        larpix_packet_type type);
larpix_packet_type larpix_uart_get_packet_type(larpix_uart_packet* packet);
void larpix_uart_set_chipid(larpix_uart_packet* packet, uint chipid);
uint larpix_uart_get_chipid(larpix_uart_packet* packet);
byte larpix_uart_compute_parity(larpix_uart_packet* packet);
void larpix_uart_set_parity(larpix_uart_packet* packet);
void larpix_uart_force_set_parity(larpix_uart_packet* packet, byte parity);
byte larpix_uart_get_parity(larpix_uart_packet* packet);
uint larpix_uart_check_parity(larpix_uart_packet* packet);

// UART access for data packets
void larpix_uart_set_channelid(larpix_uart_packet* packet, uint channelid);
uint larpix_uart_get_channelid(larpix_uart_packet* packet);
void larpix_uart_set_timestamp(larpix_uart_packet* packet, ulong timestamp);
ulong larpix_uart_get_timestamp(larpix_uart_packet* packet);
void larpix_uart_set_dataword(larpix_uart_packet* packet, uint dataword);
uint larpix_uart_get_dataword(larpix_uart_packet* packet);
void larpix_uart_set_fifohalfflag(larpix_uart_packet* packet, byte fifohalfflag);
byte larpix_uart_get_fifohalfflag(larpix_uart_packet* packet);
void larpix_uart_set_fifofullflag(larpix_uart_packet* packet, byte fifofullflag);
byte larpix_uart_get_fifofullflag(larpix_uart_packet* packet);

// UART access for config packets
void larpix_uart_set_register(larpix_uart_packet* packet, uint address);
uint larpix_uart_get_register(larpix_uart_packet* packet);
void larpix_uart_set_register_data(larpix_uart_packet* packet, uint value);
uint larpix_uart_get_register_data(larpix_uart_packet* packet);

// UART access for test packets
uint larpix_uart_get_test_counter(larpix_uart_packet* packet);

// Configuration packet
void larpix_config_init_defaults(larpix_configuration* config);

// Configuration packet read/write to UART packet
void larpix_config_write_all(larpix_configuration* config,
        larpix_uart_packet packets[LARPIX_NUM_CONFIG_REGISTERS]);
uint larpix_config_read_all(larpix_configuration* config,
        larpix_uart_packet packets[LARPIX_NUM_CONFIG_REGISTERS]);
void larpix_config_write_pixel_trim_threshold(larpix_configuration* config,
        larpix_uart_packet* packet, uint channelid);
uint larpix_config_read_pixel_trim_threshold(larpix_configuration* config,
        larpix_uart_packet* packet, uint channelid);
void larpix_config_write_global_threshold(larpix_configuration* config,
        larpix_uart_packet* packet);
uint larpix_config_read_global_threshold(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_csa_gain_and_bypasses(larpix_configuration* config,
        larpix_uart_packet* packet);
uint larpix_config_read_csa_gain_and_bypasses(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_csa_bypass_select(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk);
uint larpix_config_read_csa_bypass_select(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_csa_monitor_select(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk);
uint larpix_config_read_csa_monitor_select(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_csa_testpulse_enable(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk);
uint larpix_config_read_csa_testpulse_enable(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_csa_testpulse_dac_amplitude(larpix_configuration* config,
        larpix_uart_packet* packet);
uint larpix_config_read_csa_testpulse_dac_amplitude(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_test_mode_xtrig_reset_diag(larpix_configuration* config,
        larpix_uart_packet* packet);
uint larpix_config_read_test_mode_xtrig_reset_diag(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_sample_cycles(larpix_configuration* config,
        larpix_uart_packet* packet);
uint larpix_config_read_sample_cycles(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_test_burst_length(larpix_configuration* config,
        larpix_uart_packet* packet, uint value_chunk);
uint larpix_config_read_test_burst_length(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_adc_burst_length(larpix_configuration* config,
        larpix_uart_packet* packet);
uint larpix_config_read_adc_burst_length(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_channel_mask(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk);
uint larpix_config_read_channel_mask(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_external_trigger_mask(larpix_configuration* config,
        larpix_uart_packet* packet, uint channel_chunk);
uint larpix_config_read_external_trigger_mask(larpix_configuration* config,
        larpix_uart_packet* packet);
void larpix_config_write_reset_cycles(larpix_configuration* config,
        larpix_uart_packet* packet, uint value_chunk);
uint larpix_config_read_reset_cycles(larpix_configuration* config,
        larpix_uart_packet* packet);

#endif //ifndef LARPIX_H
