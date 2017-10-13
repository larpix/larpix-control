#include <stdio.h>
#include "larpix.h"

int main()
{
    larpix_connection _c;
    larpix_connection* c = &_c;

    larpix_default_connection(c);
    uint status = larpix_connect(c);
    if(status != 0)
    {
        printf("Could not connect (exit code %d)\n", status);
        return 1;
    }
    FT_PROGRAM_DATA eeprom;
    char Manufacturer[32];
    char ManId[16];
    char Description[64];
    char SerialNumber[16];
    eeprom.Signature1 = 0;
    eeprom.Signature2 = 0xFFFFFFFF;
    eeprom.Version = 3;
    eeprom.Manufacturer = Manufacturer;
    eeprom.ManufacturerId = ManId;
    eeprom.Description = Description;
    eeprom.SerialNumber = SerialNumber;
    c->pin_io_directions = 0x03;
    status = FT_EE_Read(c->ft_handle, &eeprom);
    if(status != 0)
    {
        printf("Could not read EEPROM (exit code %d)\n", status);
    }
    printf("VendorId: 0x%04X\n", eeprom.VendorId);
    printf("ProductId: 0x%04X\n", eeprom.ProductId);
    printf("Manufacturer: %s\n", eeprom.Manufacturer);
    printf("ManufacturerId: %s\n", eeprom.ManufacturerId);
    printf("Description: %s\n", eeprom.Description);
    printf("SerialNumber: %s\n", eeprom.SerialNumber);
    printf("MaxPower; %d\n", eeprom.MaxPower);
    printf("PnP; %d\n", eeprom.PnP);
    printf("SelfPowered; %d\n", eeprom.SelfPowered);
    printf("RemoteWakeup; %d\n", eeprom.RemoteWakeup);
    printf("PullDownEnable7;%d\n", eeprom.PullDownEnable7);
    printf("SerNumEnable7;  %d\n", eeprom.SerNumEnable7);
    printf("ALSlowSlew;     %d\n", eeprom.ALSlowSlew);
    printf("ALSchmittInput; %d\n", eeprom.ALSchmittInput);
    printf("ALDriveCurrent; %d\n", eeprom.ALDriveCurrent);
    printf("AHSlowSlew;     %d\n", eeprom.AHSlowSlew);
    printf("AHSchmittInput; %d\n", eeprom.AHSchmittInput);
    printf("AHDriveCurrent; %d\n", eeprom.AHDriveCurrent);
    printf("BLSlowSlew;     %d\n", eeprom.BLSlowSlew);
    printf("BLSchmittInput; %d\n", eeprom.BLSchmittInput);
    printf("BLDriveCurrent; %d\n", eeprom.BLDriveCurrent);
    printf("BHSlowSlew;     %d\n", eeprom.BHSlowSlew);
    printf("BHSchmittInput; %d\n", eeprom.BHSchmittInput);
    printf("BHDriveCurrent; %d\n", eeprom.BHDriveCurrent);
    printf("IFAIsFifo7;     %d\n", eeprom.IFAIsFifo7);
    printf("IFAIsFifoTar7;  %d\n", eeprom.IFAIsFifoTar7);
    printf("IFAIsFastSer7;  %d\n", eeprom.IFAIsFastSer7);
    printf("AIsVCP7;	    %d\n", eeprom.AIsVCP7);
    printf("IFBIsFifo7;     %d\n", eeprom.IFBIsFifo7);
    printf("IFBIsFifoTar7;  %d\n", eeprom.IFBIsFifoTar7);
    printf("IFBIsFastSer7;  %d\n", eeprom.IFBIsFastSer7);
    printf("BIsVCP7;	    %d\n", eeprom.BIsVCP7);
    printf("PowerSaveEnable;%d\n", eeprom.PowerSaveEnable);

    eeprom.AIsVCP7 = 0;
    eeprom.IFAIsFifo7 = 0;
    status = FT_EE_Program(c->ft_handle, &eeprom);


    status = larpix_configure_ftdi(c);
    if(status != 0)
    {
        printf("Could not configure (exit code %d)\n", status);
    }
    larpix_uart_packet p;
    larpix_uart_set_packet_type(&p, LARPIX_PACKET_CONFIG_WRITE);
    larpix_uart_set_chipid(&p, 12);
    larpix_uart_set_parity(&p);
    larpix_data data_array[10];
    for(uint i = 0; i < 10; ++i)
    {
        larpix_data* data = data_array + i;
        larpix_data_init_high(data);
        larpix_data_set_clk(data, 0);
        status = larpix_uart_to_data(&p, data, 1, 50 * i);
    }
    uint num_bytes_written = larpix_write_data(c, data_array, 10,
            LARPIX_BUFFER_SIZE);
    printf("Wrote %d bytes to FTDI chip\n", num_bytes_written);

    larpix_disconnect(c);
    return 0;
}
