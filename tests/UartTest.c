#include "CuTest.h"
#include "larpix.h"

void test_str(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    p.data[10] = 1;
    p.data[20] = 1;
    p.data[30] = 1;
    char buffer[55];
    buffer[54] = '\0';
    larpix_uart_str(&p, buffer, 54);
    char correct_answer[55];
    correct_answer[54] = '\0';
    for(uint i = 0; i < 54; ++i)
    {
        correct_answer[i] = '0';
    }
    // the str method reverses the order of the data so that the LSB is
    // all the way to the right (i.e. highest array index)
    correct_answer[43] = '1';
    correct_answer[33] = '1';
    correct_answer[23] = '1';
    CuAssertStrEquals(tc, correct_answer, buffer);
}

void test_init_zeros(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    for(uint i = 0; i < LARPIX_UART_SIZE; ++i)
    {
        CuAssertIntEquals(tc, 0, p.data[i]);
    }
}

void test_set_packet_type(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_packet_type(&p, LARPIX_PACKET_DATA);
    CuAssertIntEquals(tc, 1, p.data[0]);
    CuAssertIntEquals(tc, 0, p.data[1]);
}

void test_get_packet_type(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    p.data[1] = 1;
    larpix_packet_type pt = larpix_uart_get_packet_type(&p);
    CuAssertIntEquals(tc, 2, (byte) pt);
}

void test_set_chipid(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_chipid(&p, 120);
    CuAssertIntEquals(tc, 0, p.data[2]);
    CuAssertIntEquals(tc, 0, p.data[3]);
    CuAssertIntEquals(tc, 0, p.data[4]);
    CuAssertIntEquals(tc, 1, p.data[5]);
    CuAssertIntEquals(tc, 1, p.data[6]);
    CuAssertIntEquals(tc, 1, p.data[7]);
    CuAssertIntEquals(tc, 1, p.data[8]);
    CuAssertIntEquals(tc, 0, p.data[9]);
}

void test_get_chipid(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_chipid(&p, 120);
    uint chipid = larpix_uart_get_chipid(&p);
    CuAssertIntEquals(tc, 120, chipid);
}

void test_compute_parity(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    byte parity = larpix_uart_compute_parity(&p);
    CuAssertIntEquals(tc, 1, parity);
    p.data[23] = 1;
    parity = larpix_uart_compute_parity(&p);
    CuAssertIntEquals(tc, 0, parity);
    p.data[51] = 1;
    parity = larpix_uart_compute_parity(&p);
    CuAssertIntEquals(tc, 1, parity);
    p.data[LARPIX_UART_PARITY] = 1;
    parity = larpix_uart_compute_parity(&p);
    CuAssertIntEquals(tc, 1, parity);
}

void test_set_parity(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_parity(&p);
    CuAssertIntEquals(tc, 1, p.data[LARPIX_UART_PARITY]);
    p.data[52] = 1;
    larpix_uart_set_parity(&p);
    CuAssertIntEquals(tc, 0, p.data[LARPIX_UART_PARITY]);
}

void test_force_set_parity(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    p.data[2] = 1;
    larpix_uart_force_set_parity(&p, 1);
    CuAssertIntEquals(tc, 1, p.data[LARPIX_UART_PARITY]);
}

void test_get_parity(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_parity(&p);
    byte parity = larpix_uart_get_parity(&p);
    CuAssertIntEquals(tc, 1, parity);
}

void test_check_parity(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    uint result = larpix_uart_check_parity(&p);
    CuAssertIntEquals(tc, 1, result); // Bad parity
    p.data[1] = 1;
    result = larpix_uart_check_parity(&p);
    CuAssertIntEquals(tc, 0, result); // Good parity
}

void test_set_channelid(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_channelid(&p, 10);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 1, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 1, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 0, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
}

void test_get_channelid(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_channelid(&p, 10);
    uint id = larpix_uart_get_channelid(&p);
    CuAssertIntEquals(tc, 10, id);
}

void test_set_timestamp(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_timestamp(&p, 0xFFFF00L);
    for(uint i = 0; i < 8; ++i)
    {
        CuAssertIntEquals(tc, 0, p.data[17 + i]);
    }
    for(uint i = 0; i < 16; ++i)
    {
        CuAssertIntEquals(tc, 1, p.data[25 + i]);
    }
}

void test_get_timestamp(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_timestamp(&p, 0xA7361FL);
    ulong timestamp = larpix_uart_get_timestamp(&p);
    // Note: there is no assert for longs so convert to double with
    // eps=0.01
    CuAssertDblEquals(tc, (double)0xA7361FL, (double) timestamp, 0.01);
}

void test_set_dataword(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_dataword(&p, 0x84);
    CuAssertIntEquals(tc, 0, p.data[41]);
    CuAssertIntEquals(tc, 0, p.data[42]);
    CuAssertIntEquals(tc, 1, p.data[43]);
    CuAssertIntEquals(tc, 0, p.data[44]);
    CuAssertIntEquals(tc, 0, p.data[45]);
    CuAssertIntEquals(tc, 0, p.data[46]);
    CuAssertIntEquals(tc, 0, p.data[47]);
    CuAssertIntEquals(tc, 1, p.data[48]);
}

void test_get_dataword(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_dataword(&p, 0x7C);
    uint dataword = larpix_uart_get_dataword(&p);
    CuAssertIntEquals(tc, 0x7C, dataword);
}

void test_set_fifohalfflag(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_fifohalfflag(&p, 1);
    CuAssertIntEquals(tc, 1, p.data[51]);
}

void test_get_fifohalfflag(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_fifohalfflag(&p, 1);
    byte flag = larpix_uart_get_fifohalfflag(&p);
    CuAssertIntEquals(tc, 1, flag);
}

void test_set_fifofullflag(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_fifofullflag(&p, 1);
    CuAssertIntEquals(tc, 1, p.data[52]);
}

void test_get_fifofullflag(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_fifofullflag(&p, 1);
    byte flag = larpix_uart_get_fifofullflag(&p);
    CuAssertIntEquals(tc, 1, flag);
}

void test_set_register(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_register(&p, 10);
    CuAssertIntEquals(tc, 0, p.data[10]);
    CuAssertIntEquals(tc, 1, p.data[11]);
    CuAssertIntEquals(tc, 0, p.data[12]);
    CuAssertIntEquals(tc, 1, p.data[13]);
    CuAssertIntEquals(tc, 0, p.data[14]);
    CuAssertIntEquals(tc, 0, p.data[15]);
    CuAssertIntEquals(tc, 0, p.data[16]);
    CuAssertIntEquals(tc, 0, p.data[17]);
}

void test_get_register(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_register(&p, 10);
    uint address = larpix_uart_get_register(&p);
    CuAssertIntEquals(tc, 10, address);
}

void test_set_register_data(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_register_data(&p, 10);
    CuAssertIntEquals(tc, 0, p.data[18]);
    CuAssertIntEquals(tc, 1, p.data[19]);
    CuAssertIntEquals(tc, 0, p.data[20]);
    CuAssertIntEquals(tc, 1, p.data[21]);
    CuAssertIntEquals(tc, 0, p.data[22]);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 0, p.data[24]);
    CuAssertIntEquals(tc, 0, p.data[25]);
}

void test_get_register_data(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    larpix_uart_set_register_data(&p, 10);
    uint data = larpix_uart_get_register_data(&p);
    CuAssertIntEquals(tc, 10, data);
}

void test_get_test_counter(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_init_zeros(&p);
    p.data[50] = 1; // 512
    p.data[10] = 1; // 4096
    uint counter = larpix_uart_get_test_counter(&p);
    CuAssertIntEquals(tc, 512 + 4096, counter);
}


CuSuite* UartGetSuite()
{
    CuSuite* suite = CuSuiteNew();

    SUITE_ADD_TEST(suite, test_str);
    SUITE_ADD_TEST(suite, test_init_zeros);
    SUITE_ADD_TEST(suite, test_set_packet_type);
    SUITE_ADD_TEST(suite, test_get_packet_type);
    SUITE_ADD_TEST(suite, test_set_chipid);
    SUITE_ADD_TEST(suite, test_get_chipid);
    SUITE_ADD_TEST(suite, test_compute_parity);
    SUITE_ADD_TEST(suite, test_set_parity);
    SUITE_ADD_TEST(suite, test_force_set_parity);
    SUITE_ADD_TEST(suite, test_get_parity);
    SUITE_ADD_TEST(suite, test_check_parity);
    SUITE_ADD_TEST(suite, test_set_channelid);
    SUITE_ADD_TEST(suite, test_get_channelid);
    SUITE_ADD_TEST(suite, test_set_timestamp);
    SUITE_ADD_TEST(suite, test_get_timestamp);
    SUITE_ADD_TEST(suite, test_set_dataword);
    SUITE_ADD_TEST(suite, test_get_dataword);
    SUITE_ADD_TEST(suite, test_set_fifohalfflag);
    SUITE_ADD_TEST(suite, test_get_fifohalfflag);
    SUITE_ADD_TEST(suite, test_set_fifofullflag);
    SUITE_ADD_TEST(suite, test_get_fifofullflag);
    SUITE_ADD_TEST(suite, test_set_register);
    SUITE_ADD_TEST(suite, test_get_register);
    SUITE_ADD_TEST(suite, test_set_register_data);
    SUITE_ADD_TEST(suite, test_get_register_data);
    SUITE_ADD_TEST(suite, test_get_test_counter);
    return suite;
}
