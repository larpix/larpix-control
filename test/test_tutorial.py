import pytest
import zmq

@pytest.fixture
def temp_logfilename():
    return 'test.h5'

def test_min_example(capsys):
    from larpix import Controller, Packet_v2
    from larpix.io import FakeIO
    from larpix.logger import StdoutLogger
    controller = Controller()
    controller.io = FakeIO()
    controller.logger = StdoutLogger(buffer_length=0)
    controller.logger.enable()
    chip1 = controller.add_chip('1-1-2', version=2)  # (access key)
    chip1.config.threshold_global = 25
    controller.write_configuration('1-1-2', chip1.config.register_map['threshold_global']) # chip key, register 64
    assert capsys.readouterr().out == '[ Key: 1-1-2 | Chip: 2 | Upstream | Write | Register: 64 | Value: 25 | Parity: 1 (valid: True) ]\nRecord: [ Key: 1-1-2 | Chip: 2 | Upstream | Write | Register: 64 | Value: 25 | Parity: 1 (valid: True) ]\n'
    packet = Packet_v2(b'\x08\x14\x15\xcd[\x07\x91@')
    packet_bytes = packet.bytes()
    pretend_input = ([packet], packet_bytes)
    controller.io.queue.append(pretend_input)
    controller.run(0.05, 'test run')
    assert capsys.readouterr().out == 'Record: [ Key: None | Chip: 2 | Downstream | Data | Channel: 5 | Timestamp: 123456789 | First packet: 0 | Dataword: 145 | Trigger: normal | Local FIFO ok | Shared FIFO ok | Parity: 0 (valid: True) ]\n'
    print(controller.reads[0])
    assert capsys.readouterr().out == '[ Key: None | Chip: 2 | Downstream | Data | Channel: 5 | Timestamp: 123456789 | First packet: 0 | Dataword: 145 | Trigger: normal | Local FIFO ok | Shared FIFO ok | Parity: 0 (valid: True) ]\n'


def test_tutorial(capsys, tmpdir, temp_logfilename):
    from larpix import Controller, Packet_v2

    from larpix.io import FakeIO
    from larpix.logger import StdoutLogger
    controller = Controller()
    controller.io = FakeIO()
    controller.logger = StdoutLogger(buffer_length=0)
    controller.logger.enable()

    chipid = 5
    chip_key = '1-1-5'
    chip5 = controller.add_chip(chip_key, version=2)
    chip5 = controller[chip_key]
    chip5 = controller[1,1,5]


    from larpix import Key
    example_key = Key(1,2,3)


    assert example_key.io_group  == 1
    assert example_key.io_channel  == 2
    assert example_key.chip_id  == 3
    example_key.to_dict()


    controller.load('controller/v2_example.json')
    print(controller.chips) # chips that have been loaded into controller
    list(controller.network[1][1]['miso_ds'].edges) # all links contained in the miso_ds graph
    list(controller.network[1][1]['miso_us'].nodes) # all nodes within the miso_us graph
    list(controller.network[1][1]['mosi'].edges) # all links within the mosi graph

    list(controller.network[1][1]['mosi'].in_edges(2)) # all links pointing to chip 2 in mosi graph
    list(controller.network[1][1]['miso_ds'].successors(3)) # all chips receiving downstream data packets from chip 3
    controller.network[1][1]['mosi'].edges[(3,2)]['uart'] # check the physical uart channel that chip 2 listens to chip 3 via
    controller.network[1][1]['mosi'].nodes[2]['root'] # check if designated root chip

    controller.init_network(1,1) # issues packets required to initialize the 1,1 hydra network
    print(controller['1-1-2'].config.chip_id)
    print(controller['1-1-3'].config.enable_miso_downstream)

    controller.reset_network(1,1)

    controller.init_network(1,1,2) # configures only chip 2
    controller.init_network(1,1,3) # configures only chip 3

    assert isinstance(controller.get_network_keys(1,1), list) # gets a list of chip keys starting at the root node and descending
    assert isinstance(controller.get_network_keys(1,1,root_first_traversal=False), list) # get list of chip keys starting at deepest chips and ascending


    chip5.config.threshold_global = 35  # entire register = 1 number
    chip5.config.enable_periodic_reset = 1  # one bit as part of a register
    chip5.config.channel_mask[20] = 1  # one bit per channel


    controller.write_configuration(chip_key)  # send all registers
    controller.write_configuration(chip_key, 32)  # send only register 32
    controller.write_configuration(chip_key, [32, 50])  # send registers 32 and 50


    threshold_global_reg = chip5.config.register_map['threshold_global']


    threshold_global_name = chip5.config.register_map_inv[64]


    packets = chip5.get_configuration_read_packets()
    bytestream = b'bytes for the config read packets'
    controller.io.queue.append((packets, bytestream))

    controller.read_configuration(chip_key)

    packets = [Packet_v2()] * 40
    bytestream = b'bytes from the first set of packets'
    controller.io.queue.append((packets, bytestream))
    packets2 = [Packet_v2()] * 30
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


    packets = [Packet_v2()] * 5
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
    packet.chip_id  # all other properties return Python numbers
    packet.chip_key # key for association to a unique chip (can be None)
    packet.parity
    packet.downstream_marker

    # data packets
    packet.channel_id
    packet.dataword
    packet.timestamp
    packet.trigger_type
    packet.local_fifo
    packet.shared_fifo
    # config packets
    packet.register_address
    packet.register_data

    # if fifo_diagnostics enabled on a given chip the timestamp of data packets
    # are interpreted differently (note that this is not done automatically and will
    # need to be performed manually on each packet)
    packet.fifo_diagnostics_enabled = True
    packet.timestamp
    packet.local_fifo_events
    packet.shared_fifo_events


    from larpix.logger import HDF5Logger
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
    packet_repr['chip_id'] # chip id for packet, e.g. 246
    packet_repr['dataword'] # list of ADC values for each packet
    packet_repr.dtype # description of data type (with names of each column)

    # all packets' ADC counts, including non-data packets
    raw_values['dataword']
    # Select based on data type using a numpy bool / "mask" array:
    raw_values['dataword'][raw_values['packet_type'] == 0] # all data packets' ADC counts

    datafile.close()

def test_running_with_bern_daq_v1():
    from larpix import Controller
    from larpix.io import ZMQ_IO

    controller = Controller()
    controller.io = ZMQ_IO(config_filepath='io/loopback.json')

    controller.load('controller/pcb-2_chip_info.json')

    for key,chip in controller.chips.items():
        chip.config.load('chip/quiet.json')
        print(key, chip.config)

def test_running_with_pacman_v1r1():
    from larpix import Controller
    from larpix.io import PACMAN_IO
    controller = Controller()
    controller.io = PACMAN_IO(config_filepath='io/pacman.json',timeout=1000)
    controller.load('controller/network-3x3-tile-channel0.json')
    assert isinstance(controller.io.ping(),dict)

    with pytest.raises(zmq.ZMQError):
        controller.io.set_vddd()
    with pytest.raises(zmq.ZMQError):
        controller.io.set_vdda()

    # First bring up the network using as few packets as possible
    controller.io.group_packets_by_io_group = False # this throttles the data rate to avoid FIFO collisions
    for io_group, io_channels in controller.network.items():
        for io_channel in io_channels:
            with pytest.raises(zmq.ZMQError):
                controller.init_network(io_group, io_channel)

    # Configure the IO for a slower UART and differential signaling
    controller.io.double_send_packets = True # double up packets to avoid 512 bug when configuring
    for io_group, io_channels in controller.network.items():
        for io_channel in io_channels:
            chip_keys = controller.get_network_keys(io_group,io_channel,root_first_traversal=False)
            for chip_key in chip_keys:
                controller[chip_key].config.clk_ctrl = 1
                controller[chip_key].config.enable_miso_differential = [1,1,1,1]
                with pytest.raises(zmq.ZMQError):
                    controller.write_configuration(chip_key, 'enable_miso_differential')
                    controller.write_configuration(chip_key, 'clk_ctrl')
    for io_group, io_channels in controller.network.items():
        for io_channel in io_channels:
            with pytest.raises(zmq.ZMQError):
                controller.io.set_uart_clock_ratio(io_channel, 4, io_group=io_group)

    controller.io.double_send_packets = False
    controller.io.group_packets_by_io_group = True
