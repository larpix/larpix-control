class IO(object):
    '''
    Base class for IO objects that explicitly describes the necessary functions
    required by any IO class implementation. Additional functions are not used
    by the larpix core classes.

    '''
    def __init__(self):
        '''
        Declaration of IO object

        :ivar is_listening: flag for ``start_listening`` and ``stop_listening`` commands

        '''
        self.is_listening = False

    @classmethod
    def encode(cls, packets):
        '''
        Encodes a list of packets into a list of IO message objects

        :param packets: ``list`` of larpix ``Packet`` objects to encode into IO messages

        :returns: ``list`` of IO messages

        '''
        pass

    @classmethod
    def decode(cls, msgs):
        '''
        Decodes a list of IO message objects into respective larpix ``Packet`` objects

        :param msgs: ``list`` of IO messages

        :returns: ``list`` of larpix ``Packet`` objects

        '''
        pass

    @classmethod
    def is_valid_chip_key(cls, key):
        '''
        Check if provided key is valid for IO implementation. Chip key should be an immutable python type and not ``tuple``

        :param key: key to check validity

        :returns: ``True`` if valid key

        '''
        if isinstance(key, (list, tuple)):
            return False
        try:
            _ = dict([(key, None)])
        except TypeError:
            return False
        return True

    @classmethod

    def parse_chip_key(cls, key):
        '''
        Translate a chip key into a dict of contained information

        :param key: chip key to parse

        :returns: ``dict`` of IO information contained in key

        '''
        if not self.is_valid_chip_key(key):
            raise ValueError('invalid chip key for IO type, see docs for description of valid chip keys')
        empty_dict = {}
        return empty_dict

    @classmethod
    def generate_chip_key(cls, **kwargs):
        '''
        Create a chip key based on supplied info, raise an error if not enough information is provided

        :returns: chip key of an immutable python type and not ``tuple``

        '''
        pass



    def send(self, packets):
        '''
        Function for sending larpix packet objects

        :param packets: ``list`` of larpix ``Packet`` objects to send via IO

        :returns: ``None``

        '''
        pass


    def start_listening(self):
        '''
        Function for starting read communications on IO

        :returns: ``None``

        '''
        self.is_listening = True


    def stop_listening(self):
        '''
        Function for halting read communications on IO

        :returns: ``None``

        '''
        self.is_listening = False


    def empty_queue(self):
        '''
        Read and remove the current items in the internal queue. The details of
        the queue implementation is left up to the specific IO class.
        Generally returns all packets that have been read since last call to
        ``start_listening`` or ``empty_queue``, whichever was most recent.

        :returns: ``tuple`` of (``list`` of ``Packet`` objects, raw bytestream)

        '''
        pass


