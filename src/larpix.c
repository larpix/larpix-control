#include "larpix.h"

int larpix_connect(larpix_connection c)
{
    FT_STATUS status = FT_Open(c.portNumber, &(c.ftHandle));
    return (int) status;
}

int larpix_disconnect(larpix_connection c)
{
    FT_STATUS status = FT_Close(&(c.ftHandle));
    return (int) status;
}
