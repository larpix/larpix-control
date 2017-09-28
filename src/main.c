#include <stdio.h>
#include "larpix.h"

int main()
{
    larpix_connection c;
    c.portNumber = 0;
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
