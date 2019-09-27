from collections import OrderedDict
import warnings
import time
import json
import math

from . import configs
from .key import Key
from .chip import Chip
from .configuration import Configuration
from .packet import Packet_v1, Packet_v2, PacketCollection

class Controller(object):
    '''
    Controls a collection of LArPix Chip objects.

    Reading data:

    The specific interface for reading data is selected by specifying
    the ``io`` attribute. These objects all have
    similar behavior for reading in new data. On initialization, the
    object will discard any LArPix packets sent from ASICs. To begin
    saving incoming packets, call ``start_listening()``.
    Data will then build up in some form of internal register or queue.
    The queue can be emptied with a call to ``read()``,
    which empties the queue and returns a list of Packet objects that
    were in the queue. The ``io`` object will still be listening for
    new packets during and after this process. If the queue/register
    fills up, data may be discarded/lost. To stop saving incoming
    packets and retrieve any packets still in the queue, call
    ``stop_listening()``. While the Controller is listening,
    packets can be sent using the appropriate methods without
    interrupting the incoming data stream.

    Properties and attributes:

    - ``chips``: the ``Chip`` objects that the controller controls
    - ``reads``: list of all the PacketCollections that have been sent
      back to this controller. PacketCollections are created by
      ``run``, ``write_configuration``, ``read_configuration``,
      ``multi_write_configuration``, ``multi_read_configuration``, and
      ``store_packets``.

    '''

    def __init__(self):
        self.chips = OrderedDict()
        self.reads = []
        self.nreads = 0
        self.io = None
        self.logger = None

    def get_chip(self, chip_key):
        '''
        Retrieve the Chip object that this Controller associates with
        the given ``chip_key``.

        '''
        chip_dict = self.chips
        try:
            return chip_dict[chip_key]
        except KeyError:
            raise ValueError('Could not find chip using key <{}> '.format(chip_key))

    def add_chip(self, chip_key):
        '''
        Add a specified chip to the Controller chips.

        param: chip_key: chip key to specify unique chip

        :returns: ``Chip`` that was added

        '''
        if chip_key in self.chips:
            raise KeyError('chip with key {} already exists!'.format(chip_key))
        self.chips[Key(chip_key)] = Chip(chip_key=chip_key)
        return self.chips[chip_key]

    def load(self, filename):
        '''
        Loads the specified file that describes the chip ids and IO network

        :param filename: File path to configuration file

        '''
        return self.load_controller(filename)

    def load_controller(self, filename):
        '''
        Loads the specified file using the basic key, chip format
        The key, chip file format is:
        ``
        {
            "name": "<system name>",
            "chip_list": [<chip keystring>,...]
        }
        ``
        The chip key is the Controller access key that gets communicated to/from
        the io object when sending and receiving packets.

        :param filename: File path to configuration file

        '''
        system_info = configs.load(filename)
        chips = {}
        for chip_keystring in system_info['chip_list']:
            chip_key = Key(str(chip_keystring))
            chips[chip_key] = Chip(chip_key=chip_key)
        self.chips = chips
        return system_info['name']

    def load_daisy_chain(self, filename, io_group=1):
        '''
        Loads the specified file in a basic daisy chain format
        Daisy chain file format is:
        ``
        {
                "name": "<board name>",
                "chip_list": [[<chip id>,<daisy chain>],...]
        }
        ``
        Position in daisy chain is specified by position in `chip_set` list
        returns board name of the loaded chipset configuration

        :param filename: File path to configuration file
        :param io_group: IO group to use for chip keys

        '''
        board_info = configs.load(filename)
        chips = {}
        for chip_info in board_info['chip_list']:
            chip_id = chip_info[0]
            io_chain = chip_info[1]
            key = Key.from_dict(io_group=1, io_channel=io_chain, chip_id=chip_id)
            chips[key] = Chip(chip_key=key)
        self.chips = chips
        return board_info['name']

    def send(self, packets):
        '''
        Send the specified packets to the LArPix ASICs.

        '''
        timestamp = time.time()
        if self.io:
            self.io.send(packets)
        else:
            warnings.warn('no IO object exists, no packets sent', RuntimeWarning)
        if self.logger:
            self.logger.record(packets, direction=self.logger.WRITE)

    def start_listening(self):
        '''
        Listen for packets to arrive.

        '''
        if self.io:
            self.io.start_listening()
        else:
            warnings.warn('no IO object exists, you have done nothing', RuntimeWarning)

    def stop_listening(self):
        '''
        Stop listening for new packets to arrive.

        '''
        if self.io:
            return self.io.stop_listening()
        else:
            warnings.warn('no IO object exists, you have done nothing', RuntimeWarning)

    def read(self):
        '''
        Read any packets that have arrived and return (packets,
        bytestream) where bytestream is the bytes that were received.

        The returned list will contain packets that arrived since the
        last call to ``read`` or ``start_listening``, whichever was most
        recent.

        '''
        timestamp = time.time()
        packets = []
        bytestream = b''
        if self.io:
            packets, bytestream = self.io.empty_queue()
        else:
            warnings.warn('no IO object exists, no packets will be received', RuntimeWarning)
        if self.logger:
            self.logger.record(packets, direction=self.logger.READ)
        return packets, bytestream

    def write_configuration(self, chip_key, registers=None, write_read=0,
            message=None):
        '''
        Send the configurations stored in chip.config to the LArPix
        ASIC.

        By default, sends all registers. If registers is an int, then
        only that register is sent. If registers is an iterable, then
        all of the registers in the iterable are sent.

        If write_read == 0 (default), the configurations will be sent
        and the current listening state will not be affected. If the
        controller is currently listening, then the listening state
        will not change and the value of write_read will be ignored. If
        write_read > 0 and the controller is not currently listening,
        then the controller will listen for ``write_read`` seconds
        beginning immediately before the packets are sent out, read the
        io queue, and save the packets into the ``reads`` data member.
        Note that the controller will only read the queue once, so if a
        lot of data is expected, you should handle the reads manually
        and set write_read to 0 (default).

        '''
        chip = self.get_chip(chip_key)
        if registers is None:
            registers = list(range(chip.config.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        if message is None:
            message = 'configuration write'
        else:
            message = 'configuration write: ' + message
        packets = chip.get_configuration_write_packets(registers)
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        mess_with_listening = write_read != 0 and not already_listening
        if mess_with_listening:
            self.start_listening()
            stop_time = time.time() + write_read
        self.send(packets)
        if mess_with_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def read_configuration(self, chip_key, registers=None, timeout=1,
            message=None):
        '''
        Send "configuration read" requests to the LArPix ASIC.

        By default, request all registers. If registers is an int, then
        only that register is reqeusted. If registers is an iterable,
        then all of the registers in the iterable are requested.

        If the controller is currently listening, then the requests
        will be sent and no change to the listening state will occur.
        (The value of ``timeout`` will be ignored.) If the controller
        is not currently listening, then the controller will listen
        for ``timeout`` seconds beginning immediately before the first
        packet is sent out, and will save any received packets in the
        ``reads`` data member.

        '''
        chip = self.get_chip(chip_key)
        if registers is None:
            registers = list(range(chip.config.num_registers))
        elif isinstance(registers, int):
            registers = [registers]
        else:
            pass
        if message is None:
            message = 'configuration read'
        else:
            message = 'configuration read: ' + message
        packets = chip.get_configuration_read_packets(registers)
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        if not already_listening:
            self.start_listening()
            stop_time = time.time() + timeout
        self.send(packets)
        if not already_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def multi_write_configuration(self, chip_reg_pairs, write_read=0,
            message=None):
        '''
        Send multiple write configuration commands at once.

        ``chip_reg_pairs`` should be a list/iterable whose elements are
        an valid arguments to ``Controller.write_configuration``,
        excluding the ``write_read`` argument. Just like in the single
        ``Controller.write_configuration``, setting ``write_read > 0`` will
        have the controller read data during and after it writes, for
        however many seconds are specified.

        Examples:

        These first 2 are equivalent and write the full configurations

        >>> controller.multi_write_configuration([chip_key1, chip_key2, ...])
        >>> controller.multi_write_configuration([(chip_key1, None), chip_key2, ...])

        These 2 write the specified registers for the specified chips
        in the specified order

        >>> controller.multi_write_configuration([(chip_key1, 1), (chip_key2, 2), ...])
        >>> controller.multi_write_configuration([(chip_key1, range(10)), chip_key2, ...])

        '''
        if message is None:
            message = 'multi configuration write'
        else:
            message = 'multi configuration write: ' + message
        packets = []
        for chip_reg_pair in chip_reg_pairs:
            if not isinstance(chip_reg_pair, tuple):
                chip_reg_pair = (chip_reg_pair, None)
            chip_key, registers = chip_reg_pair
            chip = self.get_chip(chip_key)
            if registers is None:
                registers = list(range(chip.config.num_registers))
            elif isinstance(registers, int):
                registers = [registers]
            else:
                pass
            one_chip_packets = chip.get_configuration_write_packets(registers)
            packets.extend(one_chip_packets)
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        mess_with_listening = write_read != 0 and not already_listening
        if mess_with_listening:
            self.start_listening()
            stop_time = time.time() + write_read
        self.send(packets)
        if mess_with_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            #time.sleep(stop_time - time.time())
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def multi_read_configuration(self, chip_reg_pairs, timeout=1,
            message=None):
        '''
        Send multiple read configuration commands at once.

        ``chip_reg_pairs`` should be a list/iterable whose elements are
        chip keys (to read entire configuration) or (chip_key, registers)
        tuples to read only the specified register(s). Registers could
        be ``None`` (i.e. all), an ``int`` for that register only, or an
        iterable of ints.

        Examples:

        These first 2 are equivalent and read the full configurations

        >>> controller.multi_read_configuration([chip_key1, chip_key2, ...])
        >>> controller.multi_read_configuration([(chip_key1, None), chip_key2, ...])

        These 2 read the specified registers for the specified chips
        in the specified order

        >>> controller.multi_read_configuration([(chip_key1, 1), (chip_key2, 2), ...])
        >>> controller.multi_read_configuration([(chip_key1, range(10)), chip_key2, ...])

        '''
        if message is None:
            message = 'multi configuration read'
        else:
            message = 'multi configuration read: ' + message
        packets = []
        for chip_reg_pair in chip_reg_pairs:
            if not isinstance(chip_reg_pair, tuple):
                chip_reg_pair = (chip_reg_pair, None)
            chip_key, registers = chip_reg_pair
            chip = self.get_chip(chip_key)
            if registers is None:
                registers = list(range(chip.config.num_registers))
            elif isinstance(registers, int):
                registers = [registers]
            else:
                pass
            one_chip_packets = chip.get_configuration_read_packets(registers)
            packets += one_chip_packets
        already_listening = False
        if self.io:
            already_listening = self.io.is_listening
        if not already_listening:
            self.start_listening()
            stop_time = time.time() + timeout
        self.send(packets)
        if not already_listening:
            sleep_time = stop_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            #time.sleep(stop_time - time.time())
            packets, bytestream = self.read()
            self.stop_listening()
            self.store_packets(packets, bytestream, message)

    def run(self, timelimit, message):
        '''
        Read data from the LArPix ASICs for the given ``timelimit`` and
        associate the received Packets with the given ``message``.

        '''
        sleeptime = 0.1
        self.start_listening()
        start_time = time.time()
        packets = []
        bytestreams = []
        while time.time() - start_time < timelimit:
            time.sleep(sleeptime)
            read_packets, read_bytestream = self.read()
            packets.extend(read_packets)
            bytestreams.append(read_bytestream)
        self.stop_listening()
        data = b''.join(bytestreams)
        self.store_packets(packets, data, message)

    def verify_configuration(self, chip_keys=None, timeout=0.1):
        '''
        Read chip configuration from specified chip(s) and return ``True`` if the
        read chip configuration matches the current configuration stored in chip instance.
        ``chip_keys`` can be a single chip key, a list of chip keys, or ``None``. If
        ``chip_keys`` is ``None`` all chips will be verified.

        Also returns a dict containing the values of registers that are different
        (read register, stored register)
        '''
        return_value = True
        different_fields = {}
        if chip_keys is None:
            return self.verify_configuration(chip_keys=list(self.chips.keys()))
        elif isinstance(chip_keys, list):
            for chip_key in chip_keys:
                match, chip_fields = self.verify_configuration(chip_keys=chip_key)
                if not match:
                    different_fields[chip_key] = chip_fields
                    return_value = False
        else:
            chip_key = chip_keys
            chip = self.get_chip(chip_key)
            self.read_configuration(chip_key, timeout=timeout)
            configuration_data = {}
            for packet in self.reads[-1]:
                if (packet.packet_type == packet.CONFIG_READ_PACKET and
                    packet.chip_key == chip_key):
                    configuration_data[packet.register_address] = packet.register_data
            expected_data = {}
            for register_address, bits in enumerate(chip.config.all_data()):
                expected_data[register_address] = int(bits.to01(),2)
            if not configuration_data == expected_data:
                return_value = False
                for register_address in expected_data:
                    if register_address in configuration_data.keys():
                        if not configuration_data[register_address] == expected_data[register_address]:
                            different_fields[register_address] = (expected_data[register_address], configuration_data[register_address])
                    else:
                        different_fields[register_address] = (expected_data[register_address], None)
        return (return_value, different_fields)

    def enable_analog_monitor(self, chip_key, channel):
        '''
        Enable the analog monitor on a single channel on the specified chip.
        Note: If monitoring a different chip, call disable_analog_monitor first to ensure
        that the monitor to that chip is disconnected.
        '''
        chip = self.get_chip(chip_key)
        if chip.asic_version == 1:
            chip.config.disable_analog_monitor()
            chip.config.enable_analog_monitor(channel)
            self.write_configuration(chip_key, chip.config.csa_monitor_select_addresses)
        elif chip.asic_version == 2:
            chip.config.csa_monitor_select = [0]*chip.config.num_channels
            chip.config.csa_monitor_select[channel] = 1
            self.write_configuration(chip_key, chip.config.register_map['csa_monitor_select'])
        else:
            raise RuntimeError('chip has invalid asic version')
        return

    def disable_analog_monitor(self, chip_key=None, channel=None):
        '''
        Disable the analog monitor for a specified chip and channel, if none are specified
        disable the analog monitor for all chips in self.chips and all channels
        '''
        if chip_key is None:
            for chip in self.chips:
                self.disable_analog_monitor(chip_key=chip_key, channel=channel)
        elif channel is None:
            for channel in range(self.get_chip(chip_key).config.num_channels):
                self.disable_analog_monitor(chip_key=chip_key, channel=channel)
        else:
            chip = self.get_chip(chip_key)
            if chip.asic_version == 1:
                chip.config.disable_analog_monitor()
                self.write_configuration(chip_key, chip.config.csa_monitor_select_addresses)
            elif chip.asic_version == 2:
                chip.config.csa_monitor_select[channel] = 0
                self.write_configuration(chip_key, chip.config.register_map['csa_monitor_select'])
            else:
                raise RuntimeError('chip has invalid asic version')
        return

    def enable_testpulse(self, chip_key, channel_list, start_dac=255):
        '''
        Prepare chip for pulsing - enable testpulser and set a starting dac value for
        specified chip/channel
        '''
        chip = self.get_chip(chip_key)
        if chip.asic_version == 1:
            chip.config.disable_testpulse()
            chip.config.enable_testpulse(channel_list)
            chip.config.csa_testpulse_dac_amplitude = start_dac
            self.write_configuration(chip_key, chip.config.csa_testpulse_enable_addresses +
                                     [chip.config.csa_testpulse_dac_amplitude_address])
        elif chip.asic_version == 2:
            chip.config.csa_testpulse_enable = [1]*chip.config.num_channels
            for channel in channel_list:
                chip.config.csa_testpulse_enable[channel] = 0
            chip.config.csa_testpulse_dac = start_dac
            self.write_configuration(chip_key, list(chip.config.register_map['csa_testpulse_dac']) + list(chip.config.register_map['csa_testpulse_enable']))
        else:
            raise RuntimeError('chip has invalid asic version')
        return

    def issue_testpulse(self, chip_key, pulse_dac, min_dac=0, read_time=0.1):
        '''
        Reduce the testpulser dac by ``pulse_dac`` and write_read to chip for
        ``read_time`` seconds

        '''
        chip = self.get_chip(chip_key)
        if chip.asic_version == 1:
            chip.config.csa_testpulse_dac_amplitude -= pulse_dac
            if chip.config.csa_testpulse_dac_amplitude < min_dac:
                raise ValueError('Minimum DAC exceeded')
            self.write_configuration(chip_key, [chip.config.csa_testpulse_dac_amplitude_address],
                                     write_read=read_time)
        elif chip.asic_version == 2:
            if chip.config.csa_testpulse_dac - pulse_dac < min_dac:
                raise ValueError('Minimum DAC exceeded')
            try:
                chip.config.csa_testpulse_dac -= pulse_dac
            except ValueError:
                raise ValueError('Minimum DAC exceeded')
            self.write_configuration(chip_key, chip.config.register_map['csa_testpulse_dac'], write_read=read_time)
        return self.reads[-1]

    def disable_testpulse(self, chip_key=None, channel_list=None):
        '''
        Disable testpulser for specified chip/channels. If none specified, disable for
        all chips/channels
        '''
        if chip_key is None:
            for chip_key in self.chips.keys():
                self.disable_testpulse(chip_key=chip_key, channel_list=channel_list)
        if channel_list is None:
            channel_list = range(self.get_chip(chip_key).config.num_channels)
            self.disable_testpulse(chip_key=chip_key, channel_list=channel_list)
        else:
            chip = self.get_chip(chip_key)
            if chip.asic_version == 1:
                chip.config.disable_testpulse(channel_list)
                self.write_configuration(chip_key, chip.conf.csa_testpulse_enable_addresses)
            elif chip.asic_version == 2:
                for channel in channel_list:
                    chip.config.csa_testpulse_enable[channel] = 1
                self.write_configuration(chip_key, chip.conf.register_map['csa_testpulse_enable'])
            else:
                raise RuntimeError('chip has invalid asic version')
        return

    def disable(self, chip_key=None, channel_list=None):
        '''
        Update channel mask to disable specified chips/channels. If none specified,
        disable all chips/channels
        '''
        if chip_key is None:
            for chip_key in self.chips.keys():
                self.disable(chip_key=chip_key, channel_list=channel_list)
        else:
            chip = self.get_chip(chip_key)
            if channel_list is None:
                channel_list = range(chip.config.num_channels)
            if chip.asic_version == 1:
                chip.config.disable_channels(channel_list)
                self.write_configuration(chip_key, Configuration.channel_mask_addresses)
            elif chip.asic_version == 2:
                for channel in channel_list:
                    chip.config.channel_mask[channel] = 1
                    self.write_configuration(chip_key, chip.config.register_map['channel_mask'])
            else:
                raise RuntimeError('chip has invalid asic version')

    def enable(self, chip_key=None, channel_list=None):
        '''
        Update channel mask to enable specified chips/channels. If none specified,
        enable all chips/channels
        '''
        if chip_key is None:
            for chip_key in self.chips.keys():
                self.enable(chip_key=chip_key, channel_list=channel_list)
        else:
            chip = self.get_chip(chip_key)
            if channel_list is None:
                channel_list = range(chip.config.num_channels)
            if chip.asic_version == 1:
                chip.config.enable_channels(channel_list)
                self.write_configuration(chip_key, Configuration.channel_mask_addresses)
            elif chip.asic_version == 2:
                for channel in channel_list:
                    chip.config.channel_mask[channel] = 0
                self.write_configuration(chip_key, chip.config.register_map['channel_mask'])
            else:
                raise RuntimeError('chip has invalid asic version')

    def store_packets(self, packets, data, message):
        '''
        Store the packets in ``self`` and in ``self.chips``

        '''
        new_packets = PacketCollection(packets, data, message)
        new_packets.read_id = self.nreads
        self.nreads += 1
        self.reads.append(new_packets)
        #self.sort_packets(new_packets)

    def sort_packets(self, collection):
        '''
        Sort the packets in ``collection`` into each chip in ``self.chips``

        '''
        by_chip_key = collection.by_chip_key()
        for chip_key in by_chip_key.keys():
            if chip_key in self.chips.keys():
                chip = self.get_chip(chip_key)
                chip.reads.append(by_chip_key[chip_key])
            elif not self._test_mode:
                print('Warning chip key {} not in chips.'.format(chip_key))

    def save_output(self, filename, message):
        '''Save the data read by each chip to the specified file.'''
        data = {}
        data['reads'] = [collection.to_dict() for collection in self.reads]
        data['chips'] = [repr(chip) for chip in self.chips.values()]
        data['message'] = message
        with open(filename, 'w') as outfile:
            json.dump(data, outfile, indent=4,
                    separators=(',',':'), sort_keys=True)
