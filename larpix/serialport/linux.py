'''
The serial port interface for linux computers (including Raspberry Pi).

It is literally just an alias of pyserial's serial.Serial class.

'''
import serial

LinuxSerialPort = serial.Serial
