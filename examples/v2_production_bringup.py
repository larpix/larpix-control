from larpix import Controller
from larpix.io import PACMAN_IO

ctl = Controller()

# Bring up communications with io groups
ctl.io = PACMAN_IO('io/production_io.json') # specifies ip addresses + etc for io groups
if not ctl.io.ping():
    raise RuntimeError

# Bring up Hydra networks
ctl.load('controller/production_hydra_networks.json') # specifies hydra network on each io channel / group
for io_group in ctl.network:
    for io_channel in ctl.network[io_group]:
        ctl.init_network(io_group, io_channel) # loads network configurations
valid, configs = ctl.verify_network() # performs read back of each chip's miso/mosi config
if not valid:
    raise RuntimeError

# Enable channels and set thresholds
for chip_key, chip in ctl.chips.items():
    chip.config.load('chip/{}.json'.format(chip_key)) # loads chip specific configurations
for chip_key, chip in ctl.chips.items():
    ctl.write_configuration(chip_key) # writes chip specific configurations
valid, configs = ctl.verify_configuration() # performs read back of each chip's full configuration
if not valid:
    raise RuntimeError

# RUN!
