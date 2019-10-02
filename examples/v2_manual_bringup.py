from larpix import Controller
from larpix.io import ZMQ_IO

ctl = Controller()

# Bring up communications with io group
ctl.io = ZMQ_IO('io/manual_io.json') # specifies ip addresses + etc for io group
ctl.io.ping()
ctl.io.reset() # be sure that chips start in default state

# Load network configuration
ctl.load('controller/testing_network.json')

# Fiddle with root chip
ctl.init_network(1,1,2)
ctl.verify_network('1-1-2')
ctl['1-1-2'].config.load('chip/manual_base.json')
ctl.write_configuration('1-1-2')
ctl.verify_configuration('1-1-2')

# do stuff

# Fiddle with next chip
ctl.init_network(1,1,3)
ctl.verify_network('1-1-3')
ctl['1-1-3'].config.load('chip/manual_base.json')
ctl.write_configuration('1-1-3')
ctl.verify_configuration('1-1-3')

# ...
