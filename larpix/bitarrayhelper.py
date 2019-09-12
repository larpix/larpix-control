'''
A module with convenience functions for bitarray.

'''
from bitarray import bitarray

def fromuint(val, nbits):
    try:
        if isinstance(nbits, slice):
            nbits = abs(nbits.stop - nbits.start)
        string = bin(val)[2:].zfill(nbits)
        return bitarray(string)
    except TypeError:
        return val

def touint(bits):
    bin_string = bits.to01()
    return int(bin_string, 2)
