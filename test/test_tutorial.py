import pytest

@pytest.fixture
def temp_logfilename():
    return 'test.h5'

def test_min_example(capsys):
    from larpix.larpix import Controller, Packet
    from larpix.io.fakeio import FakeIO
    from larpix.logger.stdout_logger import StdoutLogger
    controller = Controller()
    controller.io = FakeIO()
    controller.logger = StdoutLogger(buffer_length=0)
    controller.logger.enable()
    chip1 = controller.add_chip('1-1-1')  # (access key)
    chip1.config.global_threshold = 25
    controller.write_configuration('1-1-1', 25) # chip key, register 25
    assert capsys.readouterr().out == '[ Chip key: 1-1-1 | Chip: 1 | Config write | Register: 25 | Value:  16 | Parity: 1 (valid: True) ]\nRecord: [ Chip key: 1-1-1 | Chip: 1 | Config write | Register: 25 | Value:  16 | Parity: 1 (valid: True) ]\n'
    packet = Packet(b'\x04\x14\x80\xc4\x03\xf2 ')
    packet_bytes = packet.bytes()
    pretend_input = ([packet], packet_bytes)
    controller.io.queue.append(pretend_input)
    controller.run(0.05, 'test run')
    print(controller.reads[0])
    assert capsys.readouterr().out == 'Record: [ Chip key: None | Chip: 1 | Data | Channel: 5 | Timestamp: 123456 | ADC data: 120 | FIFO Half: False | FIFO Full: False | Parity: 1 (valid: True) ]\n[ Chip key: None | Chip: 1 | Data | Channel: 5 | Timestamp: 123456 | ADC data: 120 | FIFO Half: False | FIFO Full: False | Parity: 1 (valid: True) ]\n'

def test_tutorial(capsys, tmpdir, temp_logfilename):
    from larpix.larpix import Controller, Packet

    from larpix.io.fakeio import FakeIO
    from larpix.logger.stdout_logger import StdoutLogger
    controller = Controller()
    controller.io = FakeIO()
    controller.logger = StdoutLogger(buffer_length=0)
    controller.logger.enable()


    chip_key = '1-1-5'
    chip5 = controller.add_chip(chip_key)
    chip5 = controller.get_chip(chip_key)


    from larpix.larpix import Key
    example_key = Key('1-2-3')


    assert example_key.io_group  == 1
    assert example_key.io_channel  == 2
    assert example_key.chip_id  == 3
    example_key.to_dict()


    chip5.config.global_threshold = 35  # entire register = 1 number
    chip5.config.periodic_reset = 1  # one bit as part of a register
    chip5.config.channel_mask[20] = 1  # one bit per channel


    controller.write_configuration(chip_key)  # send all registers
    controller.write_configuration(chip_key, 32)  # send only register 32
    controller.write_configuration(chip_key, [32, 50])  # send registers 32 and 50


    global_threshold_reg = chip5.config.global_threshold_address


    packets = chip5.get_configuration_packets(Packet.CONFIG_READ_PACKET)
    bytestream = b'bytes for the config read packets'
    controller.io.queue.append((packets, bytestream))

    controller.read_configuration(chip_key)

    packets = [Packet()] * 40
    bytestream = b'bytes from the first set of packets'
    controller.io.queue.append((packets, bytestream))
    packets2 = [Packet()] * 30
    bytestream2 = b'bytes from the second set of packets'
    controller.io.queue.append((packets2, bytestream2))

    controller.start_listening()
    # Data arrives...
    packets, bytestream = controller.read()
    # More data arrives...
    packets2, bytestream2 = controller.read()
    controller.stop_listening()
    message = 'First data arrived!'
    message2 = 'More data arrived!'
    controller.store_packets(packets, bytestream, message)
    controller.store_packets(packets, bytestream2, message2)


    packets = [Packet()] * 5
    bytestream = b'[bytes from read #%d] '
    for i in range(100):
        controller.io.queue.append((packets, bytestream%i))

    duration = 0.1  # seconds
    message = '10-second data run'
    controller.run(duration, message)


    run1 = controller.reads[0]
    first_packet = run1[0]  # Packet object
    first_ten_packets = run1[0:10]  # smaller PacketCollection object

    first_packet_bits = run1[0, 'bits']  # string representation of bits in packet
    first_ten_packet_bits = run1[0:10, 'bits']  # list of strings


    print(run1)  # prints the contents of the packets
    print(run1[10:30])  # prints 20 packets from the middle of the run


    packet = run1[0]
    # all packets
    packet.packet_type  # unique in that it gives the bits representation
    packet.chipid  # all other properties return Python numbers
    packet.chip_key # key for association to a unique chip
    packet.parity_bit_value
    # data packets
    packet.channel_id
    packet.dataword
    packet.timestamp
    assert packet.fifo_half_flag in (1, 0)
    assert packet.fifo_full_flag in (1, 0)
    # config packets
    packet.register_address
    packet.register_data
    # test packets
    packet.test_counter


    from larpix.logger.h5_logger import HDF5Logger
    controller.logger = HDF5Logger(filename=temp_logfilename, directory=str(tmpdir), buffer_length=10000) # a filename of None uses the default filename formatting
    controller.logger.enable() # opens hdf5 file and starts tracking all communications

    controller.logger = HDF5Logger(filename=temp_logfilename,
            directory=str(tmpdir), enabled=True)

    controller.verify_configuration()
    controller.logger.flush()


    controller.logger.disable() # stop tracking
    # any communication here is ignored
    controller.logger.enable() # start tracking again
    controller.logger.is_enabled() # returns True if tracking


    controller.logger.disable()


    import h5py
    datafile = h5py.File(tmpdir.join(temp_logfilename))


    assert '_header' in datafile.keys()
    assert 'packets' in datafile.keys()
    assert 'messages' in datafile.keys()
    assert list(datafile['_header'].attrs) == ['created', 'modified', 'version']


    raw_value = datafile['packets'][0] # e.g. (b'0-246', 3, 246, 1, 1, -1, -1, -1, -1, -1, -1, 0, 0)
    raw_values = datafile['packets'][-100:] # last 100 packets in file


    packet_repr = raw_values[0:1]
    packet_repr['chip_key'] # chip key for packet, e.g. b'1-1-246'
    packet_repr['adc_counts'] # list of ADC values for each packet
    packet_repr.dtype # description of data type (with names of each column)


    datafile.close()

def test_running_with_bern_daq():
    from larpix.larpix import Controller
    from larpix.io.zmq_io import ZMQ_IO

    controller = Controller()
    controller.io = ZMQ_IO(config_filepath='io/loopback.json')

    controller.load('controller/pcb-2_chip_info.json')

    for key,chip in controller.chips.items():
        chip.config.load('chip/quiet.json')
        print(key, chip.config)
