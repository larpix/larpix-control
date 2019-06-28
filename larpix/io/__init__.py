import bidict

from larpix import configs

class IO(object):
    '''
    Base class for IO objects that explicitly describes the necessary functions
    required by any IO class implementation. Additional functions are not used
    by the larpix core classes.

    '''
    _valid_config_types = ['io']
    _valid_config_classes = ['IO']

    def __init__(self):
        '''
        Declaration of IO object

        :ivar is_listening: flag for ``start_listening`` and ``stop_listening``
        :ivar default_filepath: default configuration path to load

        '''
        self.default_filepath = 'io/default.json'

        self.is_listening = False
        self._io_group_table = bidict.bidict()

    def load(self, filepath=None):
        '''
        Loads a specified IO configuration

        :param filepath: path to io configuration file (JSON)

        '''
        if filepath is None:
            filepath = self.default_filepath
        config = configs.load(filepath)
        if (config['_config_type'] not in self._valid_config_types or
            config['io_class'] not in self._valid_config_classes):
            raise RuntimeError('Invalid configuration type for {}'.format(type(self).__name__))
        self._io_group_table = bidict.bidict(config['io_group'])

    def encode(self, packets):
        '''
        Encodes a list of packets into a list of IO message objects

        :param packets: ``list`` of larpix ``Packet`` objects to encode into IO messages

        :returns: ``list`` of IO messages

        '''
        pass

    def decode(self, msgs, **kwargs):
        '''
        Decodes a list of IO message objects into respective larpix ``Packet`` objects

        :param msgs: ``list`` of IO messages

        :param kwargs: additional contextual information required to decode messages (implementation specific)

        :returns: ``list`` of larpix ``Packet`` objects

        '''
        pass

    def parse_chip_key(self, key):
        '''
        Translate a chip key into a dict of contained information

        :param key: chip key to parse

        :returns: ``dict`` of IO information contained in key

        '''
        empty_dict = {}
        return empty_dict

    def generate_chip_key(self, **kwargs):
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


