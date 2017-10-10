#include "CuTest.h"
#include "larpix.h"

void test_write_pixel_trim_threshold(CuTest* tc)
{
    larpix_configuration c;
    c.pixel_trim_thresholds[3] = 7;
    larpix_uart_packet p;
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

CuSuite* ConfigGetSuite()
{
    CuSuite* suite = CuSuiteNew();

    SUITE_ADD_TEST(suite, test_write_pixel_trim_threshold);
    return suite;
}
