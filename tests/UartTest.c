#include "CuTest.h"
#include "larpix.h"

void TestSetPacketType(CuTest* tc)
{
    larpix_uart_packet p;
    larpix_uart_set_packet_type(&p, LARPIX_PACKET_DATA);
    CuAssertIntEquals(tc, 1, p.data[0]);
    CuAssertIntEquals(tc, 0, p.data[1]);
}

CuSuite* UartGetSuite()
{
    CuSuite* suite = CuSuiteNew();

    SUITE_ADD_TEST(suite, TestSetPacketType);
    return suite;
}
