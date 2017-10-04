'''
A module to interface with the larpix-control C library using Python's
ctypes module.

'''

import ctypes as c

larpix = c.cdll.LoadLibrary('../bin/larpix.so')

class larpix_data(c.Structure):
    _fields_ = [("bits", (c.c_ubyte * larpix.larpix_buffer_size()) * 8)]

class larpix_connection(c.Structure):
    _fields_ = [
            ("ft_handle", c.c_void_p),
            ("port_number", c.c_int),
            ("clk_divisor", c.c_uint),
            ("pin_io_directions", c.c_ubyte),
            ("bit_mode", c.c_ubyte),
            ("timeout", c.c_uint),
            ("usb_transfer_size", c.c_uint)
            ]

class larpix_uart_packet(c.Structure):
    _fields_ = [("data", c.c_ubyte * larpix.larpix_uart_size())]

larpix_packet_type = {
        "data": c.c_int(0),
        "test": c.c_int(1),
        "config_write": c.c_int(2),
        "config_read": c.c_int(3)
        }
