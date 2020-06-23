from larpix import Controller
from larpix.io import PACMAN_IO

ctl = Controller()

# Bring up communications with io groups
ctl.io = PACMAN_IO('io/testing_io.json') # specifies ip addresses + etc for io groups
if not ctl.io.ping():
    raise RuntimeError

# Load network configuration
ctl.load('controller/testing_network.json')
for io_group in ctl.network:
    for io_channel in ctl.network[io_group]:
        chip_keys = ctl.get_network_keys(io_group, io_channel)
        for chip_key in chip_keys:
            # Initialize network node
            chip_id = chip_key.chip_id
            ctl.init_network(io_group, io_channel, chip_id) # assume upstream nodes of chip key are configured and configure specified chip
            ok, diff = ctl.verify_network(chip_key)
            if not ok:
                raise RuntimeError

            ctl[chip_key].config.load('chip/testing_base.json') # load base configuration (don't specify chip_id, mosi, miso_*)
            ctl.write_configuration(chip_key)
            ok, diff = ctl.verify_configuration(chip_key)
            if not ok:
                raise RuntimeError

            # Chip level tests
            ctl[chip_key].config.global_threshold = 30
            ctl.write_configuration(chip_key, chip_key.config.register_map['global_threshold'])
            # etc

            test_channel = 4
            ctl.enable_analog_monitor(chip_key, test_channel)
            # etc
        chip_keys = [link[1] for link in us_subnetwork.out_edges(chip_keys)]

# Full system tests
