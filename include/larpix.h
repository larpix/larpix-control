#include <ftd2xx/ftd2xx.h>

typedef struct larpix_connection
{
    FT_HANDLE ftHandle;
    int portNumber;
} larpix_connection;

int larpix_connect(larpix_connection c);
int larpix_disconnect(larpix_connection c);
