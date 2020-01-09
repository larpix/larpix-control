class Key(object):
    '''
    A unique specification for routing data to a particular detector sub-system.
    At the core, a key is represented by 3-unsigned 1-byte integer fields which
    refer to an id code within a layer of the LArPix DAQ system heirarchy.
    Field 0 represents the io group id number, field 1 represents the io
    channel connecting to a MISO/MOSI pair, and field 2 represents the chip
    id. The io group is the device controlling a set of MOSI/MISO pairs, the
    io channel is a single MOSI/MISO pair controlling a collection of LArPix
    asics, and the chip id uniquely identifies a chip on a single MISO/MISO
    network.

    Each field should be a 1-byte unsigned integer (0-255) providing a unique
    lookup value for each component in the system. The id values of 0 and 255
    are reserved for special functionality.

    A key can be specified by a string of ``'<io group>-<io channel>-<chip id>'``, by io group, io channel, and chip id, or by
    using other Keys.

    Keys are hashed by their string representation and are equivalent to their
    string representation so::

        key = Key(1,1,1) # io group, io channel, chip id
        key == Key('1-1-1') # True
        key == Key(key) # True

        key == '1-1-1' # True
        key == (1,1,1) # True

        d = { key: 'example' }
        d[key] == 'example' # True
        d['1-1-1'] == 'example' # True

    Keys are "psuedo-immutable", i.e. you cannot change a Key's io_group,
    io_channel, or chip_id after it has been created.

    '''
    key_delimiter = '-'
    key_format = key_delimiter.join(('{io_group}', '{io_channel}', '{chip_id}'))

    def __init__(self, *args):
        self._initialized = False
        if len(args) == 3:
            self.io_group = args[0]
            self.io_channel = args[1]
            self.chip_id = args[2]
        elif len(args) == 1:
            if isinstance(args[0], Key):
                self.io_group = args[0].io_group
                self.io_channel = args[0].io_channel
                self.chip_id = args[0].chip_id
            elif isinstance(args[0], bytes):
                self.keystring = str(args[0].decode("utf-8"))
            else:
                self.keystring = str(args[0])
        else:
            raise TypeError('Key() takes 1 or 3 arguments ({} given)'.format(len(args)))
        self._initialized = True

    def __repr__(self):
        return 'Key(\'{}\')'.format(self.keystring)

    def __str__(self):
        return self.keystring

    def __eq__(self, other):
        if isinstance(other, Key):
            return self.io_group == other.io_group and \
            self.io_channel == other.io_channel \
            and self.chip_id == other.chip_id
        if isinstance(other, tuple):
            return self.io_group == other[0] and self.io_channel == other[1] \
            and self.chip_id == other[2]
        if str(self) == str(other):
            return True
        return False

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(str(self))

    def __getitem__(self, index):
        return (self.io_group, self.io_channel, self.chip_id)[index]

    @property
    def keystring(self):
        '''
        Key string specifying key io group, io channel, and chip id in the
        format: ``'<io group>-<io channel>-<chip id>'``
        '''
        return Key.key_format.format(
                io_group = self.io_group,
                io_channel = self.io_channel,
                chip_id = self.chip_id
            )

    @keystring.setter
    def keystring(self, val):
        if self._initialized:
            raise AttributeError('keystring cannot be modified')
        if not isinstance(val, str):
            raise TypeError('keystring must be str')
        parsed_keystring = val.split(Key.key_delimiter)
        if len(parsed_keystring) != 3:
            raise ValueError('invalid keystring formatting')
        self.io_group = int(parsed_keystring[0])
        self.io_channel = int(parsed_keystring[1])
        self.chip_id = int(parsed_keystring[2])

    @property
    def chip_id(self):
        '''
        1-byte unsigned integer representing the physical chip id (hardwired for
        v1 ASICs, assigned dynamically for v2 ASICs)
        '''
        return self._chip_id

    @chip_id.setter
    def chip_id(self, val):
        if self._initialized:
            raise AttributeError('chipid cannot be modified')
        chip_id = int(val)
        if chip_id > 255 or chip_id < 0:
            raise ValueError('chip_id must be 1-byte ({} invalid)'.format(chip_id))
        self._chip_id = chip_id

    @property
    def io_channel(self):
        '''
        1-byte unsigned integer representing the physical io channel. This
        identifies a single MOSI/MISO pair used to communicate with a single
        network of up to 254 chips.
        '''
        return self._io_channel

    @io_channel.setter
    def io_channel(self, val):
        if self._initialized:
            raise AttributeError('io_channel cannot be modified')
        io_channel = int(val)
        if io_channel > 255 or io_channel < 0:
            raise ValueError('io_channel must be 1-byte ({} invalid)'.format(io_channel))
        self._io_channel = io_channel

    @property
    def io_group(self):
        '''
        1-byte unsigned integer representing the physical device used to read
        out up to 254 io channels.
        '''
        return self._io_group

    @io_group.setter
    def io_group(self, val):
        if self._initialized:
            raise AttributeError('io_group cannot be modified')
        io_group = int(val)
        if io_group > 255 or io_group < 0:
            raise ValueError('io_group must be 1-byte ({} invalid)'.format(io_group))
        self._io_group = io_group

    @staticmethod
    def is_valid_keystring(keystring):
        '''
        Check if keystring can be interpreted as a larpix.Key

        :returns: ``True`` if the keystring can be interpreted as a larpix.Key
        '''
        if not isinstance(keystring, str):
            return False
        try:
            key = Key(keystring)
        except ValueError:
            return False
        return True

    def to_dict(self):
        '''
        Convert Key into a dict

        :returns: ``dict`` with ``'io_group'``, ``'io_channel'``, and ``'chip_id'``
        '''
        return_dict = dict(
                io_group = self.io_group,
                io_channel = self.io_channel,
                chip_id = self.chip_id
            )
        return return_dict

    @staticmethod
    def from_dict(d):
        '''
        Convert a dict into a Key object, dict must contain ``'io_group'``,
        ``'io_channel'``, and ``'chip_id'``

        :returns: ``Key``
        '''
        req_keys = ('io_group', 'io_channel', 'chip_id')
        if not all([key in d for key in req_keys]):
            raise ValueError('dict must specify {}'.format(req_keys))
        return Key(d['io_group'], d['io_channel'], d['chip_id'])
