'''
A module with convenience functions for bitarray.

'''
from bitarray import bitarray

def fromuint(val, nbits, endian='big'):
    try:
        if isinstance(nbits, slice):
            nbits = abs(nbits.stop - nbits.start)
        if endian[0] == 'b':
            string = bin(val)[2:].zfill(nbits)
            return bitarray(string)
        string = bin(val)[-1:1:-1].ljust(nbits,'0')
        return bitarray(string)
    except TypeError:
        return val

def touint(bits, endian='big'):
    bin_string = bits.to01()
    if endian[0] == 'b':
        return int(bin_string, 2)
    return int(bin_string[::-1], 2)
