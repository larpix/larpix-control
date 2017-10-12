#include "CuTest.h"
#include "larpix.h"

void test_init_high(CuTest* tc)
{
    larpix_data d;
    larpix_data_init_high(&d);
    for(uint i = 0; i < 8; ++i)
    {
        for(uint j = 0; j < LARPIX_BUFFER_SIZE; ++j)
        {
            CuAssertIntEquals(tc, 1, d.bits[i][j]);
        }
    }
}

void test_init_low(CuTest* tc)
{
    larpix_data d;
    larpix_data_init_low(&d);
    for(uint i = 0; i < 8; ++i)
    {
        for(uint j = 0; j < LARPIX_BUFFER_SIZE; ++j)
        {
            CuAssertIntEquals(tc, 0, d.bits[i][j]);
        }
    }
}

void test_set_clk(CuTest* tc)
{
    larpix_data d;
    larpix_data_set_clk(&d, 2);
    byte* ch2 = d.bits[2];
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        CuAssertIntEquals(tc, i & 1, ch2[i]);
    }
}

void test_data_to_array(CuTest* tc)
{
    larpix_data d;
    larpix_data_init_low(&d);
    larpix_data_set_clk(&d, 1);
    byte array[LARPIX_BUFFER_SIZE];
    larpix_data_to_array(&d, array, LARPIX_BUFFER_SIZE);
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        CuAssertIntEquals(tc, (i % 2) * 2, array[i]);
    }
}

void test_array_to_data(CuTest* tc)
{
    larpix_data d;
    byte array[LARPIX_BUFFER_SIZE];
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        array[i] = i % 0x100;
    }
    larpix_array_to_data(&d, array, LARPIX_BUFFER_SIZE);
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        CuAssertIntEquals(tc, i & 0x1, d.bits[0][i]);
        CuAssertIntEquals(tc, (i & 0x2) >> 1, d.bits[1][i]);
        CuAssertIntEquals(tc, (i & 0x4) >> 2, d.bits[2][i]);
        CuAssertIntEquals(tc, (i & 0x8) >> 3, d.bits[3][i]);
        CuAssertIntEquals(tc, (i & 0x10) >> 4, d.bits[4][i]);
        CuAssertIntEquals(tc, (i & 0x20) >> 5, d.bits[5][i]);
        CuAssertIntEquals(tc, (i & 0x40) >> 6, d.bits[6][i]);
        CuAssertIntEquals(tc, (i & 0x80) >> 7, d.bits[7][i]);
    }
}

void test_set_bitstream(CuTest* tc)
{
    larpix_data d;
    larpix_data_init_high(&d);
    byte array[LARPIX_BUFFER_SIZE];
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        array[i] = (i & 8) >> 3;
    }
    larpix_data_set_bitstream(&d, array, 2, 100);
    for(uint i = 0; i < 100; ++i)
    {
        CuAssertIntEquals(tc, array[i], d.bits[2][i]);
    }
    for(uint i = 100; i < LARPIX_BUFFER_SIZE; ++i)
    {
        CuAssertIntEquals(tc, 1, d.bits[2][i]);
    }
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        CuAssertIntEquals(tc, 1, d.bits[1][i]);
        CuAssertIntEquals(tc, 1, d.bits[3][i]);
    }
}

void test_get_bitstream(CuTest* tc)
{
    larpix_data d;
    larpix_data_init_high(&d);
    byte array[LARPIX_BUFFER_SIZE];
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        array[i] = (i & 8) >> 3;
    }
    larpix_data_set_bitstream(&d, array, 2, 100);
    larpix_data_get_bitstream(&d, array, 1, LARPIX_BUFFER_SIZE);
    for(uint i = 0; i < LARPIX_BUFFER_SIZE; ++i)
    {
        CuAssertIntEquals(tc, 1, array[i]);
    }
    larpix_data_get_bitstream(&d, array, 2, 100);
    for(uint i = 0; i < 100; ++i)
    {
        CuAssertIntEquals(tc, d.bits[2][i], array[i]);
    }
    for(uint i = 100; i < LARPIX_BUFFER_SIZE; ++i)
    {
        CuAssertIntEquals(tc, 1, array[i]);
    }
}

CuSuite* DataGetSuite()
{
    CuSuite* suite = CuSuiteNew();

    SUITE_ADD_TEST(suite, test_init_high);
    SUITE_ADD_TEST(suite, test_init_low);
    SUITE_ADD_TEST(suite, test_set_clk);
    SUITE_ADD_TEST(suite, test_data_to_array);
    SUITE_ADD_TEST(suite, test_array_to_data);
    SUITE_ADD_TEST(suite, test_set_bitstream);
    SUITE_ADD_TEST(suite, test_get_bitstream);
    return suite;
}
