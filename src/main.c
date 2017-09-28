#include <stdio.h>
#include "larpix.h"

int main()
{
    larpix_connection _c;
    larpix_connection* c = &_c;
    int status = 0;

    if((status = larpix_connect(c)) == 0)
    {
        printf("Successful connection!\n");
    }
    else
    {
        printf("Error with status code %d\n", status);
    }
    larpix_disconnect(c);
    return 0;
}
