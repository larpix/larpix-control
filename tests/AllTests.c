#include <stdio.h>

#include "CuTest.h"

CuSuite* UartGetSuite();
CuSuite* ConfigGetSuite();

void RunAllTests(void)
{
	CuString *output = CuStringNew();
	CuSuite* suite = CuSuiteNew();

	CuSuiteAddSuite(suite, UartGetSuite());
	CuSuiteAddSuite(suite, ConfigGetSuite());

	CuSuiteRun(suite);
	CuSuiteSummary(suite, output);
	CuSuiteDetails(suite, output);
	printf("%s\n", output->buffer);
}

int main(void)
{
	RunAllTests();
}
