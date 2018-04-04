'''
A module with convenience functions for bitarray.

'''
from bitarray import bitarray

def fromuint(val, nbits):
    if isinstance(val, bitarray):
        return val
    if isinstance(nbits, slice):
        nbits = abs(nbits.stop - nbits.start)
    bin_string = bin(val)[2:]
    padding = '0' * (nbits - len(bin_string))
    return bitarray(padding + bin_string)

def touint(bits):
    bin_string = bits.to01()
    return int(bin_string, 2)
