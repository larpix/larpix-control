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
    return suite;
}
