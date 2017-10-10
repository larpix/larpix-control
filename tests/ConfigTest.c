#include "CuTest.h"
#include "larpix.h"

void test_write_pixel_trim_threshold(CuTest* tc)
{
    larpix_configuration c;
    c.pixel_trim_thresholds[3] = 7;
    larpix_uart_packet p;
    larpix_config_write_pixel_trim_threshold(&c, &p, 3);
    CuAssertIntEquals(tc, 0, p.data[23]);
    CuAssertIntEquals(tc, 1, p.data[24]);
    CuAssertIntEquals(tc, 1, p.data[25]);
    CuAssertIntEquals(tc, 1, p.data[26]);
    CuAssertIntEquals(tc, 0, p.data[27]);

}

CuSuite* ConfigGetSuite()
{
    CuSuite* suite = CuSuiteNew();

    SUITE_ADD_TEST(suite, test_write_pixel_trim_threshold);
    return suite;
}
