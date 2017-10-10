#include "CuTest.h"
#include "larpix.h"

void test_write_pixel_trim_threshold(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.pixel_trim_thresholds[3] = 7;
    larpix_config_write_pixel_trim_threshold(&c, &p, 3);
    CuAssertIntEquals(tc, 1, p.data[10]);
    CuAssertIntEquals(tc, 1, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 0, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 0, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 1, p.data[18]);
    CuAssertIntEquals(tc, 1, p.data[19]);
    CuAssertIntEquals(tc, 1, p.data[20]);
    CuAssertIntEquals(tc, 0, p.data[21]);
    CuAssertIntEquals(tc, 0, p.data[22]);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 0, p.data[25]);
}

void test_read_pixel_trim_threshold(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[10] = 1;
    p.data[11] = 1;
    p.data[18] = 1;
    p.data[19] = 1;
    p.data[20] = 1;
    larpix_config_read_pixel_trim_threshold(&c, &p);
    CuAssertIntEquals(tc, 7, c.pixel_trim_thresholds[3]);
}

void test_write_global_threshold(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.global_threshold = 180;
    larpix_config_write_global_threshold(&c, &p);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 0, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 0, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 0, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 1, p.data[20]);
    CuAssertIntEquals(tc, 0, p.data[21]);
    CuAssertIntEquals(tc, 1, p.data[22]);
    CuAssertIntEquals(tc, 1, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 1, p.data[25]);
}

void test_read_global_threshold(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[15] = 1;
    p.data[20] = 1;
    p.data[22] = 1;
    p.data[23] = 1;
    p.data[25] = 1;
    larpix_config_read_global_threshold(&c, &p);
    CuAssertIntEquals(tc, 180, c.global_threshold);
}

void test_write_csa_gain_and_bypasses(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.csa_gain = 1;
    c.csa_bypass = 1;
    c.internal_bypass = 1;
    larpix_config_write_csa_gain_and_bypasses(&c, &p);
    CuAssertIntEquals(tc, 1, p.data[10]);
    CuAssertIntEquals(tc, 0, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 0, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 1, p.data[18]);
    CuAssertIntEquals(tc, 1, p.data[19]);
    CuAssertIntEquals(tc, 1, p.data[20]);
    CuAssertIntEquals(tc, 0, p.data[21]);
    CuAssertIntEquals(tc, 0, p.data[22]);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 0, p.data[25]);
}

void test_read_csa_gain_and_bypasses(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[10] = 1;
    p.data[15] = 1;
    p.data[18] = 1;
    p.data[19] = 1;
    p.data[20] = 1;
    larpix_config_read_csa_gain_and_bypasses(&c, &p);
    CuAssertIntEquals(tc, 1, c.csa_gain);
    CuAssertIntEquals(tc, 1, c.csa_bypass);
    CuAssertIntEquals(tc, 1, c.internal_bypass);
}

void test_write_csa_bypass_select(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.csa_bypass_select[3] = 1;
    c.csa_bypass_select[7] = 1;
    larpix_config_write_csa_bypass_select(&c, &p, 0);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 1, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 0, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 0, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 0, p.data[20]);
    CuAssertIntEquals(tc, 1, p.data[21]);
    CuAssertIntEquals(tc, 0, p.data[22]);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 1, p.data[25]);
}

void test_read_csa_bypass_select(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[11] = 1;
    p.data[15] = 1;
    p.data[21] = 1;
    p.data[25] = 1;
    larpix_config_read_csa_bypass_select(&c, &p);
    CuAssertIntEquals(tc, 1, c.csa_bypass_select[3]);
    CuAssertIntEquals(tc, 0, c.csa_bypass_select[5]);
    CuAssertIntEquals(tc, 1, c.csa_bypass_select[7]);
}

void test_write_csa_monitor_select(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.csa_monitor_select[10] = 0;
    c.csa_monitor_select[12] = 0;
    larpix_config_write_csa_monitor_select(&c, &p, 1);
    CuAssertIntEquals(tc, 1, p.data[10]);
    CuAssertIntEquals(tc, 1, p.data[11]);
    CuAssertIntEquals(tc, 1, p.data[12]);
    CuAssertIntEquals(tc, 0, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 1, p.data[18]);
    CuAssertIntEquals(tc, 1, p.data[19]);
    CuAssertIntEquals(tc, 0, p.data[20]);
    CuAssertIntEquals(tc, 1, p.data[21]);
    CuAssertIntEquals(tc, 0, p.data[22]);
    CuAssertIntEquals(tc, 1, p.data[23]);
    CuAssertIntEquals(tc, 1, p.data[24]);
    CuAssertIntEquals(tc, 1, p.data[25]);
}

void test_read_csa_monitor_select(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[10] = 1;
    p.data[11] = 1;
    p.data[12] = 1;
    p.data[15] = 1;
    p.data[18] = 1;
    p.data[19] = 1;
    p.data[21] = 1;
    p.data[23] = 1;
    p.data[24] = 1;
    p.data[25] = 1;
    larpix_config_read_csa_monitor_select(&c, &p);
    CuAssertIntEquals(tc, 0, c.csa_monitor_select[10]);
    CuAssertIntEquals(tc, 0, c.csa_monitor_select[12]);
    CuAssertIntEquals(tc, 1, c.csa_monitor_select[15]);
}

void test_write_csa_testpulse_enable(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.csa_testpulse_enable[20] = 1;
    c.csa_testpulse_enable[23] = 1;
    larpix_config_write_csa_testpulse_enable(&c, &p, 2);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 0, p.data[11]);
    CuAssertIntEquals(tc, 1, p.data[12]);
    CuAssertIntEquals(tc, 1, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 0, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 0, p.data[20]);
    CuAssertIntEquals(tc, 0, p.data[21]);
    CuAssertIntEquals(tc, 1, p.data[22]);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 1, p.data[25]);
}

void test_read_csa_testpulse_enable(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[12] = 1;
    p.data[13] = 1;
    p.data[15] = 1;
    p.data[22] = 1;
    p.data[25] = 1;
    larpix_config_read_csa_testpulse_enable(&c, &p);
    CuAssertIntEquals(tc, 0, c.csa_testpulse_enable[18]);
    CuAssertIntEquals(tc, 1, c.csa_testpulse_enable[20]);
    CuAssertIntEquals(tc, 1, c.csa_testpulse_enable[23]);
}

void test_write_csa_testpulse_dac_amplitude(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.csa_testpulse_dac_amplitude = 204;
    larpix_config_write_csa_testpulse_dac_amplitude(&c, &p);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 1, p.data[11]);
    CuAssertIntEquals(tc, 1, p.data[12]);
    CuAssertIntEquals(tc, 1, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 0, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 1, p.data[20]);
    CuAssertIntEquals(tc, 1, p.data[21]);
    CuAssertIntEquals(tc, 0, p.data[22]);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 1, p.data[24]);
    CuAssertIntEquals(tc, 1, p.data[25]);
}

void test_read_csa_testpulse_dac_amplitude(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[11] = 1;
    p.data[12] = 1;
    p.data[13] = 1;
    p.data[15] = 1;
    p.data[20] = 1;
    p.data[21] = 1;
    p.data[24] = 1;
    p.data[25] = 1;
    larpix_config_read_csa_testpulse_dac_amplitude(&c, &p);
    CuAssertIntEquals(tc, 204, c.csa_testpulse_dac_amplitude);
}

void test_write_test_mode_xtrig_reset_diag(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.test_mode = 1;
    c.cross_trigger_mode = 1;
    c.periodic_reset = 1;
    c.fifo_diagnostic = 1;
    larpix_config_write_test_mode_xtrig_reset_diag(&c, &p);
    CuAssertIntEquals(tc, 1, p.data[10]);
    CuAssertIntEquals(tc, 1, p.data[11]);
    CuAssertIntEquals(tc, 1, p.data[12]);
    CuAssertIntEquals(tc, 1, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 1, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 1, p.data[20]);
    CuAssertIntEquals(tc, 1, p.data[21]);
    CuAssertIntEquals(tc, 1, p.data[22]);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 0, p.data[25]);
}

void test_read_test_mode_xtrig_reset_diag(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[10] = 1;
    p.data[11] = 1;
    p.data[12] = 1;
    p.data[13] = 1;
    p.data[15] = 1;
    p.data[18] = 1;
    p.data[20] = 1;
    p.data[21] = 1;
    p.data[22] = 1;
    larpix_config_read_test_mode_xtrig_reset_diag(&c, &p);
    CuAssertIntEquals(tc, 1, c.test_mode);
    CuAssertIntEquals(tc, 1, c.cross_trigger_mode);
    CuAssertIntEquals(tc, 1, c.periodic_reset);
    CuAssertIntEquals(tc, 1, c.fifo_diagnostic);
}

void test_write_sample_cycles(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.sample_cycles = 49;
    larpix_config_write_sample_cycles(&c, &p);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 0, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 0, p.data[13]);
    CuAssertIntEquals(tc, 1, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 1, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 0, p.data[20]);
    CuAssertIntEquals(tc, 0, p.data[21]);
    CuAssertIntEquals(tc, 1, p.data[22]);
    CuAssertIntEquals(tc, 1, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 0, p.data[25]);
}

void test_read_sample_cycles(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[14] = 1;
    p.data[15] = 1;
    p.data[18] = 1;
    p.data[22] = 1;
    p.data[23] = 1;
    larpix_config_read_sample_cycles(&c, &p);
    CuAssertIntEquals(tc, 49, c.sample_cycles);
}

void test_write_test_burst_length(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.test_burst_length[0] = 100;
    larpix_config_write_test_burst_length(&c, &p, 0);
    CuAssertIntEquals(tc, 1, p.data[10]);
    CuAssertIntEquals(tc, 0, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 0, p.data[13]);
    CuAssertIntEquals(tc, 1, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 0, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 1, p.data[20]);
    CuAssertIntEquals(tc, 0, p.data[21]);
    CuAssertIntEquals(tc, 0, p.data[22]);
    CuAssertIntEquals(tc, 1, p.data[23]);
    CuAssertIntEquals(tc, 1, p.data[24]);
    CuAssertIntEquals(tc, 0, p.data[25]);
}

void test_read_test_burst_length(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[10] = 1;
    p.data[14] = 1;
    p.data[15] = 1;
    p.data[20] = 1;
    p.data[23] = 1;
    p.data[24] = 1;
    larpix_config_read_test_burst_length(&c, &p);
    CuAssertIntEquals(tc, 100, c.test_burst_length[0]);
}

void test_write_adc_burst_length(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.adc_burst_length = 20;
    larpix_config_write_adc_burst_length(&c, &p);
    CuAssertIntEquals(tc, 1, p.data[10]);
    CuAssertIntEquals(tc, 1, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 0, p.data[13]);
    CuAssertIntEquals(tc, 1, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 0, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 1, p.data[20]);
    CuAssertIntEquals(tc, 0, p.data[21]);
    CuAssertIntEquals(tc, 1, p.data[22]);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 0, p.data[25]);
}

void test_read_adc_burst_length(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[10] = 1;
    p.data[11] = 1;
    p.data[14] = 1;
    p.data[15] = 1;
    p.data[20] = 1;
    p.data[22] = 1;
    larpix_config_read_adc_burst_length(&c, &p);
    CuAssertIntEquals(tc, 20, c.adc_burst_length);
}

void test_write_channel_mask(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.channel_mask[4] = 1;
    c.channel_mask[7] = 1;
    larpix_config_write_channel_mask(&c, &p, 0);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 0, p.data[11]);
    CuAssertIntEquals(tc, 1, p.data[12]);
    CuAssertIntEquals(tc, 0, p.data[13]);
    CuAssertIntEquals(tc, 1, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 0, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 0, p.data[20]);
    CuAssertIntEquals(tc, 0, p.data[21]);
    CuAssertIntEquals(tc, 1, p.data[22]);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 1, p.data[25]);
}

void test_read_channel_mask(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[12] = 1;
    p.data[14] = 1;
    p.data[15] = 1;
    p.data[22] = 1;
    p.data[25] = 1;
    larpix_config_read_channel_mask(&c, &p);
    CuAssertIntEquals(tc, 1, c.channel_mask[4]);
    CuAssertIntEquals(tc, 0, c.channel_mask[5]);
    CuAssertIntEquals(tc, 1, c.channel_mask[7]);
}

void test_write_external_trigger_mask(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.external_trigger_mask[4] = 0;
    c.external_trigger_mask[7] = 0;
    larpix_config_write_external_trigger_mask(&c, &p, 0);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 0, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 1, p.data[13]);
    CuAssertIntEquals(tc, 1, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 1, p.data[18]);
    CuAssertIntEquals(tc, 1, p.data[19]);
    CuAssertIntEquals(tc, 1, p.data[20]);
    CuAssertIntEquals(tc, 1, p.data[21]);
    CuAssertIntEquals(tc, 0, p.data[22]);
    CuAssertIntEquals(tc, 1, p.data[23]);
    CuAssertIntEquals(tc, 1, p.data[24]);
    CuAssertIntEquals(tc, 0, p.data[25]);
}

void test_read_external_trigger_mask(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[13] = 1;
    p.data[14] = 1;
    p.data[15] = 1;
    p.data[18] = 1;
    p.data[19] = 1;
    p.data[20] = 1;
    p.data[21] = 1;
    p.data[23] = 1;
    p.data[24] = 1;
    larpix_config_read_external_trigger_mask(&c, &p);
    CuAssertIntEquals(tc, 0, c.external_trigger_mask[4]);
    CuAssertIntEquals(tc, 1, c.external_trigger_mask[5]);
    CuAssertIntEquals(tc, 0, c.external_trigger_mask[7]);
}

void test_write_reset_cycles(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    c.reset_cycles[0] = 100;
    larpix_config_write_reset_cycles(&c, &p, 0);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 0, p.data[11]);
    CuAssertIntEquals(tc, 1, p.data[12]);
    CuAssertIntEquals(tc, 1, p.data[13]);
    CuAssertIntEquals(tc, 1, p.data[14]);
    CuAssertIntEquals(tc, 1, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
    CuAssertIntEquals(tc, 0, p.data[18]);
    CuAssertIntEquals(tc, 0, p.data[19]);
    CuAssertIntEquals(tc, 1, p.data[20]);
    CuAssertIntEquals(tc, 0, p.data[21]);
    CuAssertIntEquals(tc, 0, p.data[22]);
    CuAssertIntEquals(tc, 1, p.data[23]);
    CuAssertIntEquals(tc, 1, p.data[24]);
    CuAssertIntEquals(tc, 0, p.data[25]);
}

void test_read_reset_cycles(CuTest* tc)
{
    larpix_configuration c;
    larpix_uart_packet p;
    larpix_config_init_defaults(&c);
    larpix_uart_init_zeros(&p);
    p.data[12] = 1;
    p.data[13] = 1;
    p.data[14] = 1;
    p.data[15] = 1;
    p.data[20] = 1;
    p.data[23] = 1;
    p.data[24] = 1;
    larpix_config_read_reset_cycles(&c, &p);
    CuAssertIntEquals(tc, 100, c.reset_cycles[0]);
}

CuSuite* ConfigGetSuite()
{
    CuSuite* suite = CuSuiteNew();

    SUITE_ADD_TEST(suite, test_write_pixel_trim_threshold);
    SUITE_ADD_TEST(suite, test_read_pixel_trim_threshold);
    SUITE_ADD_TEST(suite, test_write_global_threshold);
    SUITE_ADD_TEST(suite, test_read_global_threshold);
    SUITE_ADD_TEST(suite, test_write_csa_gain_and_bypasses);
    SUITE_ADD_TEST(suite, test_read_csa_gain_and_bypasses);
    SUITE_ADD_TEST(suite, test_write_csa_bypass_select);
    SUITE_ADD_TEST(suite, test_read_csa_bypass_select);
    SUITE_ADD_TEST(suite, test_write_csa_monitor_select);
    SUITE_ADD_TEST(suite, test_read_csa_monitor_select);
    SUITE_ADD_TEST(suite, test_write_csa_testpulse_enable);
    SUITE_ADD_TEST(suite, test_read_csa_testpulse_enable);
    SUITE_ADD_TEST(suite, test_write_csa_testpulse_dac_amplitude);
    SUITE_ADD_TEST(suite, test_read_csa_testpulse_dac_amplitude);
    SUITE_ADD_TEST(suite, test_write_test_mode_xtrig_reset_diag);
    SUITE_ADD_TEST(suite, test_read_test_mode_xtrig_reset_diag);
    SUITE_ADD_TEST(suite, test_write_sample_cycles);
    SUITE_ADD_TEST(suite, test_read_sample_cycles);
    SUITE_ADD_TEST(suite, test_write_test_burst_length);
    SUITE_ADD_TEST(suite, test_read_test_burst_length);
    SUITE_ADD_TEST(suite, test_write_adc_burst_length);
    SUITE_ADD_TEST(suite, test_read_adc_burst_length);
    SUITE_ADD_TEST(suite, test_write_channel_mask);
    SUITE_ADD_TEST(suite, test_read_channel_mask);
    SUITE_ADD_TEST(suite, test_write_external_trigger_mask);
    SUITE_ADD_TEST(suite, test_read_external_trigger_mask);
    SUITE_ADD_TEST(suite, test_write_reset_cycles);
    SUITE_ADD_TEST(suite, test_read_reset_cycles);
    return suite;
}
