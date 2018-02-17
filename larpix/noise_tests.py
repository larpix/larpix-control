'''
Run basic noise tests for chips
  Note: Reset chips before each test.
'''

from __future__ import absolute_import
from larpix.quickstart import quickcontroller
from larpix.quickstart import disable_chips
from larpix.larpix import (flush_logger, PacketCollection)
import math
import time
import json
import os

def pulse_channel(controller, chip_idx=0, pulse_channel=0, n_pulses=100,
                  pulse_dac=6, testpulse_dac_max=235, testpulse_dac_min=40):
    '''Simple script to pulse and then listen to a given channel'''
    # Get chip under test
    chip = controller.chips[chip_idx]
    # Initialize DAC level
    chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
    controller.write_configuration(chip,46)
    time.sleep(0.5) # Settle CSA
    dac_level = testpulse_dac_max
    # Configure chip for pulsing one channel
    chip.config.csa_testpulse_enable = [1]*32 # Disable all other channels
    chip.config.csa_testpulse_enable[pulse_channel] = 0 # Connect
    controller.write_configuration(chip,[42,43,44,45])
    #
    # Pulse chip n times
    controller.run(0.2, 'clear buffer')
    for pulse_idx in range(n_pulses):
        if dac_level < (testpulse_dac_min + pulse_dac):
            # Reset DAC level if it is too low to issue pulse
            chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
            controller.write_configuration(chip,46)
            time.sleep(0.5) # Settle CSA
            controller.run(0.2, 'clear buffer')
            print('  Reset DAC value')
            dac_level = testpulse_dac_max
        # Issue pulse
        dac_level -= pulse_dac  # Negative DAC step mimics electron arrival
        chip.config.csa_testpulse_dac_amplitude = dac_level
        controller.write_configuration(chip,46,write_read=0.3)
        print '  pulse %d (DAC=%d): %d packets' % (pulse_idx, dac_level,
                                                   len(controller.reads[-1]))
    # Reset DAC level, and disconnect channel
    chip.config.csa_testpulse_enable = [1]*32 # Disconnect
    controller.write_configuration(chip,[42,43,44,45]) # testpulse
    chip.config.csa_testpulse_dac_amplitude = 0
    controller.write_configuration(chip,46)
    return


def check_chip_status(controller, chip_idx=0, channel_ids = range(32),
                      global_thresh=60, pulse_dac=20):
    '''Quick check of system status using internal pulser on each channel'''
    # Get chip under test
    chip = controller.chips[chip_idx]
    # First, ensure all channels disabled
    chip.config.channel_mask = [1]*32 # Disable all channels
    controller.write_configuration(chip, range(52,56))
    # Ensure all pixel trims at max
    chip.config.pixel_trim_thresholds = [31]*32
    controller.write_configuration(chip, range(32))
    # Set moderate global threshold
    chip.config.global_threshold = global_thresh
    controller.write_configuration(chip, 32)
    # Clear buffer
    controller.run(0.2, 'clear buffer')
    # Check each channel
    for chanid in channel_ids:
        print ''
        print 'Checking chip - channel: %d - %d' % (chip_idx, chanid)
        chip.config.channel_mask[chanid] = 0 # Enable channel
        controller.write_configuration(chip, range(52,56))
        # Read to check that noise level is managable
        controller.run(0.2, 'clear buffer')
        controller.run(0.2, 'noise check chan = %d' % chanid)
        n_noise_packets = len(controller.reads[-1])
        # Pulse check
        pulse_channel(controller, chip_idx=chip_idx, pulse_channel=chanid,
                      n_pulses=2, pulse_dac=pulse_dac)
        n_pulse_packets = [len(controller.reads[-2]), len(controller.reads[-1])]
        print ' Noise packets: %d' % (n_noise_packets)
        print ' Pulse packets: %r' % (n_pulse_packets)
        # Be sure to disable after test
        chip.config.channel_mask = [1]*32 # Disable all channels
        controller.write_configuration(chip, range(52,56))
    return


def find_channel_thresholds(controller=None, board='pcb-1', chip_idx=0,
                            channel_list=range(32), output_directory='.',
                            saturation_level=5, run_time=1, reset_cycles=4096,
                            threshold_min_coarse=20, threshold_max_coarse=40,
                            threshold_step_coarse=1, max_level=100,
                            trim_min=0, trim_max=31, trim_step=1,
                            pulse_dac=10):
    ''' Scans through global threshold then channel trims to determine a chip configuration
    that produces less than ``saturation_level/run_time``Hz/channel of triggers '''
    print('begin threshold scan')
    # Create controller and initialize chips to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        controller.disable()
        controller.run(2,'clear buffer')
        config_ok, different_registers = controller.verify_configuration()
        if config_ok:
            print('  new controller created')
        else:
            print('  configuration error')
            print('  different registers: %s' % str(different_registers))
    chip = controller.chips[chip_idx]
    chip_id = chip.chip_id
    print('configuring chip %d for scan' % chip_id)
    # Save current configuration in a temporary file
    temp_filename = '.config_%s.json' % time.strftime('%Y_%m_%d_%H_%M_%S',time.localtime())
    print('temporarily storing previous configuration: %s' % temp_filename)
    chip.config.write(temp_filename,force=True)
    # Set up chip configuration
    controller.disable(chip_id=chip_id)
    chip.config.global_threshold = threshold_max_coarse
    chip.config.pixel_trim_thresholds = [trim_max]*32
    chip.config.reset_cycles = reset_cycles
    registers_to_write = range(33) + [52,53,54,55] + [60,61,62]
    controller.write_configuration(chip, registers_to_write)
    config_ok, different_registers = controller.verify_configuration(chip_id=chip_id)
    if not config_ok:
        print('  configuration error')
        print('  different registers: %s' % str(different_registers))
    # Check for high rate channels
    print('checking rate at max threshold')
    controller.enable(chip_id=chip_id, channel_list=channel_list)
    high_rate_channels = set()
    while True:
        controller.run(run_time,'checking for high rate channels')
        packets_by_channel = [0]*32
        for channel in channel_list:
            for packet in controller.reads[-1]:
                if packet.chipid == chip.chip_id:
                    packets_by_channel[packet.channel_id] += 1
        saturated_channels = [channel for channel,npackets in enumerate(packets_by_channel)
                              if npackets >= max_level]
        high_rate_channels = set(saturated_channels + list(high_rate_channels))
        print('  channels at saturation: %s' % str(saturated_channels))
        if len(saturated_channels) == 0:
            break
        print('  disabling')
        controller.disable(chip_id=chip_id, channel_list=high_rate_channels)
        controller.run(2,'clear buffer')
    if len(high_rate_channels) > 0:
        high_rate_channels = list(high_rate_channels)
        print('  disabled high rate channels: %s' % str(high_rate_channels))
    enabled_channels = [channel for channel,mask in enumerate(chip.config.channel_mask[:])
                        if not mask]
    # Run a quick threshold scan to determine global threshold
    print('begin coarse scan')
    coarse_scan_results = quick_scan_threshold(controller=controller, board=board,
                                               chip_idx=chip_idx,
                                               channel_list=enabled_channels,
                                               threshold_min_coarse=threshold_min_coarse,
                                               threshold_max_coarse=threshold_max_coarse,
                                               threshold_step_coarse=threshold_step_coarse,
                                               saturation_level=saturation_level,
                                               run_time=run_time,
                                               reset_cycles=reset_cycles)
    print('coarse scan complete')
    channel_coarse_thresholds = [threshold_min_coarse]*32
    for channel in coarse_scan_results:
        if len(coarse_scan_results[channel]['threshold']) > 0:
            channel_coarse_thresholds[channel] = coarse_scan_results[channel]['threshold'][-1]
    coarse_threshold = max([threshold
                            for channel,threshold in enumerate(channel_coarse_thresholds)
                            if channel in enabled_channels])
    print('global threshold: %d' % coarse_threshold)
    chip.config.global_threshold = coarse_threshold
    controller.write_configuration(chip, 32)
    # Run fine scan to determine pixel thresholds
    print('begin fine scan')
    fine_scan_results = simultaneous_scan_trim(controller=controller, board=board,
                                               chip_idx=chip_idx,
                                               channel_list=enabled_channels,
                                               trim_min=trim_min, trim_max=trim_max,
                                               trim_step=trim_step,
                                               saturation_level=saturation_level,
                                               max_level=max_level,
                                               reset_cycles=reset_cycles,
                                               global_threshold=coarse_threshold,
                                               run_time=run_time)
    print('fine scan complete')
    channel_trims = [trim_max]*32
    for channel in fine_scan_results:
        channel_trims[channel] = fine_scan_results[channel]['trims'][-1]
    for channel in channel_list:
        chip.config.pixel_trim_thresholds[channel] = channel_trims[channel]
    controller.write_configuration(chip, range(32))
    # Pulse channels to test sensitivity
    controller.run(2,'clear buffer')
    controller.run(run_time,'check rate')
    channel_rate = [0]*32
    for packet in controller.reads[-1]:
        if packet.chipid == chip_id:
            channel_rate[packet.channel_id] += 1./run_time
    print('check rate: %.2f Hz / %d channels' % (float(len(controller.reads[-1]))/run_time,
                                                 len(enabled_channels)))
    print('testing sensitivity (DAC=%d)' % pulse_dac)
    controller.enable_testpulse(chip_id=chip_id, channel_list=channel_list)
    controller.issue_testpulse(chip_id=chip_id, pulse_dac=pulse_dac)
    packets_received = [0]*32
    for packet in controller.reads[-1]:
        if packet.chipid == chip_id:
            packets_received[packet.channel_id] += 1
    print('  channel - packets received')
    for channel,npackets in enumerate(packets_received):
        print('  %d - %d' % (channel,npackets))
    controller.disable_testpulse(chip_id=chip_id)
    # Print summary of scan
    print('find_channel_thresholds report:')
    print('  channel\tenabled?\tsat thresh (global)\ttrim\trate (Hz)\tpulse npackets')
    for channel in range(32):
        if channel in channel_list:
            print('  %d\t\t%d\t\t%d\t\t%d\t\t%.2f\t\t%d' % (channel, (channel in 
                                                                      enabled_channels),
                                                  channel_coarse_thresholds[channel],
                                                  channel_trims[channel],
                                                  channel_rate[channel],
                                                  packets_received[channel]))
    print('global threshold: %d' % coarse_threshold)
    print('channel mask: %s' % str([int(not channel in enabled_channels)
                                    for channel in range(32)]))
    print('pixel trim thresholds: %s' % str(channel_trims))
    config_filename = '%s/c%d_%s.json' % (output_directory, chip_id,
                                          time.strftime('%Y_%m_%d_%H_%M_%S',
                                                        time.localtime()))
    return_config = chip.config
    # Save config to file
    try:
        chip.config.write(filename=config_filename)
        print('configuration saved: %s' % config_filename)
    except IOError:
        user_input = ''
        while not user_input in ['y','n','Y','N']:
            user_input = raw_input('  force write config?\t')
        if user_input in ['y', 'Y']:
            try:
                chip.config.write(filename=config_filename)
                print('configuration saved: %s' % config_filename)
            except:
                print('  write failed!')

    # Return chip to original state
    controller.disable(chip_id=chip.chip_id)
    chip.config.load(temp_filename)
    controller.write_configuration(chip)
    os.remove(temp_filename)
    if not controller.verify_configuration(chip_id=chip.chip_id)[0]:
        print('  warning: could not verify original chip state')
    if close_controller:
        controller.serial_close()

    # Return configuration with appropriate channel mask, threshold, and trims
    return return_config

def simultaneous_scan_trim(controller=None, board='pcb-5', chip_idx=0,
                           channel_list=range(32),
                           trim_min=0, trim_max=31, trim_step=1, saturation_level=1000,
                           max_level=1200, reset_cycles = 4096,
                           global_threshold=30, run_time=0.1):
    # Create controller and initialize chips to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        disable_chips(controller)
        print('  created controller')
    # Get chip under test
    chip = controller.chips[chip_idx]
    # Temporarily store chip configuration
    temp_filename = '.config_%s.json' % time.strftime('%Y_%m_%d_%H_%M_%S',time.localtime())
    print('temporarily storing previous configuration: %s' % temp_filename)
    chip.config.write(temp_filename,force=True)
    # Configure chip for one channel operation
    print('testing chip',chip.chip_id)
    results = {}
    chip.config.global_threshold = global_threshold
    chip.config.disable_channels()
    controller.write_configuration(chip,range(52,56))
    time.sleep(1)
    chip.config.enable_channels(channel_list)
    chip.config.reset_cycles = reset_cycles
    print('  writing config')
    controller.write_configuration(chip,range(60,62))
    controller.write_configuration(chip,[32,52,53,54,55])
    print('  reading config')
    controller.read_configuration(chip)
    print('  set mask')
    # Prepare to scan
    controller.run(5,'clear buffer')
    n_packets = []
    adc_means = []
    adc_rmss = []
    channel_trims = {}
    channel_npackets = {}
    scan_completed = {}
    for channel in channel_list:
        channel_trims[channel] = []
        channel_npackets[channel] = []
        scan_completed[channel] = False
    next_trim = trim_max
    while next_trim >= trim_min:
        # Set global coarse threshold
        for channel in channel_list:
            if not scan_completed[channel]:
                chip.config.pixel_trim_thresholds[channel] = next_trim
                channel_trims[channel].append(next_trim)
        controller.write_configuration(chip,range(0,32))
        print('    set trim %d' % next_trim)
        print('    clear buffer (quick)')
        controller.run(0.1,'clear buffer')
        del controller.reads[-1]
        #if threshold == thresholds[0]:
        if len(controller.reads) > 0 and len(controller.reads[-1]) > 0:
        #if True:
            # Flush buffer for first cycle
            print('    clear buffer (slow)')
            controller.run(2,'clear buffer')
        controller.reads = []
        # Collect data
        print('    reading')
        controller.run(run_time,'scan trim')
        print('    done reading (read %d)' % len(controller.reads[-1]))
        # Process data
        packets = controller.reads[-1]
        packets_by_channel = {}
        for channel in channel_list:
            packets_by_channel[channel] = []
        for packet in controller.reads[-1]:
            if packet.chipid == chip.chip_id:
                packets_by_channel[packet.channel_id] += [packet]

        if any([len(packets_by_channel[channel])>=max_level for channel in channel_list]):
            # turn off noisy channels
            for channel in channel_list:
                if len(packets_by_channel[channel])>=max_level:
                    print('  disabling ch%d' % channel)
                    chip.config.disable_channels([channel])
                    controller.write_configuration(chip,range(52,56),write_read=1)
                    del controller.reads[-1]
            continue
        else:
            next_trim -= trim_step

        for channel in channel_list:
            if len(packets_by_channel[channel])>0:
                channel_npackets[channel].append(len(packets_by_channel[channel]))
                print('  %d %d %d %d' % (channel, channel_trims[channel][-1],
                                         len(packets_by_channel[channel]),
                                         scan_completed[channel]))
            if len(packets_by_channel[channel])>=saturation_level:
                scan_completed[channel] = True

        if all([scan_completed[channel] for channel in scan_completed]):
            break
    print('channel summary (channel, trim, npackets):')
    for channel in channel_list:
        results[channel] = {'trims':channel_trims[channel],
                            'npackets':channel_npackets[channel],
                            'complete':scan_completed[channel]}
        if len(results[channel]['npackets'])>0:
            print('%d %d %d' % (channel, results[channel]['trims'][-1],
                                results[channel]['npackets'][-1]))
        else:
            print('%d %d 0' % (channel, results[channel]['trims'][-1]))

    # Return chip to original state
    controller.disable(chip_id=chip.chip_id)
    chip.config.load(temp_filename)
    controller.write_configuration(chip)
    os.remove(temp_filename)
    if not controller.verify_configuration(chip_id=chip.chip_id)[0]:
        print('  warning: could not verify original chip state')
    if close_controller:
        controller.serial_close()
    return results

def simultaneous_scan_trim_with_communication(controller=None, board='pcb-5', chip_idx=0,
                                              channel_list=range(32),
                                              trim_min=0, trim_max=31, trim_step=1,
                                              saturation_level=10, reset_cycles = 4096,
                                              max_level=100, writes=100,
                                              global_threshold=30, run_time=0.1):
    # Create controller and initialize chips to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        disable_chips(controller)
        print('  created controller')
    # Get chip under test
    chip = controller.chips[chip_idx]
    results = {}
    global_threshold_orig = chip.config.global_threshold
    pixel_trim_thresholds_orig = chip.config.pixel_trim_thresholds
    channel_mask_orig = chip.config.channel_mask[:]
    print('testing chip',chip.chip_id)
    # Configure chip for one channel operation
    chip.config.global_threshold = global_threshold
    chip.config.disable_channels()
    controller.write_configuration(chip,range(52,56))
    controller.run(0.1,'clear buffer')
    chip.config.enable_channels(channel_list)
    chip.config.reset_cycles = reset_cycles
    print('  writing config')
    controller.write_configuration(chip,range(60,62)) # reset cycles
    controller.write_configuration(chip,[32,52,53,54,55])
    print('  reading config')
    controller.read_configuration(chip)
    print('  set mask')
    # Prepare to scan
    controller.run(5,'clear buffer')
    n_packets = []
    adc_means = []
    adc_rmss = []
    disabled_channels = []
    channel_trims = {}
    channel_npackets = {}
    scan_completed = {}
    for channel in channel_list:
        channel_trims[channel] = []
        channel_npackets[channel] = []
        scan_completed[channel] = False
    next_trim = trim_max
    while next_trim >= trim_min:
        # Set global coarse threshold
        for channel in channel_list:
            if not scan_completed[channel]:
                chip.config.pixel_trim_thresholds[channel] = next_trim
                channel_trims[channel].append(next_trim)
        controller.write_configuration(chip,range(0,32))
        print('    set trim %d' % next_trim)
        print('    clear buffer (quick)')
        controller.run(0.1,'clear buffer')
        del controller.reads[-1]
        #if threshold == thresholds[0]:
        if len(controller.reads) > 0 and len(controller.reads[-1]) > 0:
        #if True:
            # Flush buffer for first cycle
            print('    clear buffer (slow)')
            controller.run(2,'clear buffer')
        controller.reads = []
        # Collect data
        print('    writing and reading')
        for write in range(writes):
            controller.write_configuration(chip, 32, write_read=run_time)
        print('    done reading')

        # Process data
        reads = controller.reads[-writes:]
        packets = PacketCollection([packet for read in reads for packet in read])
        print('    read %d' % len(packets))
        packets_by_channel = {}
        for channel in channel_list:
            packets_by_channel[channel] = []
        for packet in packets:
            if packet.chipid == chip.chip_id:
                packets_by_channel[packet.channel_id] += [packet]
        if any([len(packets_by_channel[channel])>max_level for channel in channel_list]):
            # turn off noisy channels
            for channel in channel_list:
                if len(packets_by_channel[channel])>max_level:
                    print('    disabling ch%d' % channel)
                    chip.config.disable_channels([channel])
                    controller.write_configuration(chip,range(52,56),write_read=1)
                    del controller.reads[-1]
                    disabled_channels.append(channel)
            continue
        else:
            next_trim -= trim_step

        for channel in channel_list:
            if len(packets_by_channel[channel])>0:
                channel_npackets[channel].append(len(packets_by_channel[channel]))
                print('  %d %d %d %d' % (channel, channel_trims[channel][-1],
                                         len(packets_by_channel[channel]),
                                         scan_completed[channel]))
            if len(packets_by_channel[channel])>=saturation_level:
                scan_completed[channel] = True

        if all([scan_completed[channel] for channel in scan_completed]):
            break
    for channel in channel_list:
        results[channel] = {'trims':channel_trims[channel],
                            'npackets':channel_npackets[channel],
                            'complete':scan_completed[channel]}
    results['disabled_channels'] = disabled_channels

    # Restore original global threshold and channel mask
    chip.config.pixel_trim_thresholds = pixel_trim_thresholds_orig
    chip.config.global_threshold = global_threshold_orig
    controller.write_configuration(chip,range(0,33))
    chip.config.channel_mask = channel_mask_orig
    controller.write_configuration(chip,[52,53,54,55])
    if close_controller:
        controller.serial_close()
    return results

def scan_trim(controller=None, board='pcb-5', chip_idx=0, channel_list=range(32),
              trim_min=0, trim_max=31, trim_step=1, saturation_level=1000,
              global_threshold=30, run_time=0.1, reset_cycles=4096):
    # Create controller and initialize chips to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        disable_chips(controller)
        print('  created controller')
    # Get chip under test
    chip = controller.chips[chip_idx]
    results = {}
    global_threshold_orig = chip.config.global_threshold
    pixel_trim_thresholds_orig = chip.config.pixel_trim_thresholds
    channel_mask_orig = chip.config.channel_mask[:]
    print('testing chip',chip.chip_id)
    for channel in channel_list:
        print('testing channel',channel)
        # Configure chip for one channel operation
        chip.config.global_threshold = global_threshold
        chip.config.channel_mask = [1,]*32
        chip.config.channel_mask[channel] = 0
        chip.config.reset_cycles = reset_cycles
        print('  writing config')
        controller.write_configuration(chip,range(60,62))
        controller.write_configuration(chip,[32,52,53,54,55])
        print('  reading config')
        controller.read_configuration(chip)
        print('  set mask')
        # Scan thresholds
        trims = range(trim_min,
                      trim_max+1,
                      trim_step)
        # Scan from high to low
        trims.reverse()
        # Prepare to scan
        controller.run(5,'clear buffer')
        n_packets = []
        adc_means = []
        adc_rmss = []
        for trim in trims:
            # Set global coarse threshold
            chip.config.pixel_trim_thresholds[channel] = trim
            controller.write_configuration(chip,range(0,32))
            print('    set threshold')
            print('    clear buffer (quick)')
            controller.run(0.1,'clear buffer')
            del controller.reads[-1]
            #if threshold == thresholds[0]:
            if len(controller.reads) > 0 and len(controller.reads[-1]) > 0:
            #if True:
                # Flush buffer for first cycle
                print('    clearing buffer')
                time.sleep(0.2)
                controller.run(2,'clear buffer')
                time.sleep(0.2)
            controller.reads = []
            # Collect data
            print('    reading')
            controller.run(run_time,'scan trim')
            print('    done reading')
            # Process data
            packets = controller.reads[-1]
            #[packet for packet in controller.reads[-1]
                      # if packet.chipid ==chip.chip_id and packet.channel_id == channel]
            adc_mean = 0
            adc_rms = 0
            if len(packets)>0:
                print('    processing packets: %d' % len(packets))
                adcs = [p.dataword for p in packets
                        if p.chipid == chip.chip_id and p.channel_id == channel]
                if len(adcs) > 0:
                    adc_mean = sum(adcs)/float(len(adcs))
                    adc_rms = (sum([abs(adc-adc_mean) for adc in adcs])
                               / float(len(adcs)))
            n_packets.append(len(packets))
            adc_means.append(adc_mean)
            adc_rmss.append(adc_rms)
            print(    '%d %d %0.2f %0.4f' % (trim, len(packets),
                                             adc_mean, adc_rms))
            if len(packets)>saturation_level:
                # Stop scanning if saturation level is hit.
                break
        results[channel] = [trims[:], n_packets[:],
                            adc_means[:], adc_rmss[:]]

    print('Summary (last trim, sat level, adc mean, adc rms):')
    for channel in results:
        print('%d %d %d %.2f %.2f' % (channel, results[channel][0][-1],
                                      results[channel][1][-1], results[channel][2][-1],
                                      results[channel][3][-1]))

    # Restore original global threshold and channel mask
    chip.config.pixel_trim_thresholds = pixel_trim_thresholds_orig
    chip.config.global_threshold = global_threshold_orig
    controller.write_configuration(chip,range(0,33))
    chip.config.channel_mask = channel_mask_orig
    controller.write_configuration(chip,[52,53,54,55])
    if close_controller:
        controller.serial_close()
    return results

def quick_scan_threshold(controller=None, board='pcb-5', chip_idx=0,
                         channel_list=range(32), threshold_min_coarse=26,
                         threshold_max_coarse=37, threshold_step_coarse=1,
                         saturation_level=1000, run_time=0.1, reset_cycles=4092):
    '''
    Enable all channels and scan thresholds until one channels reaches saturation
    Disable that channel and continue
    '''
    # Create controller and initialize chips to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        disable_chips(controller)
        print('created controller')
    chip = controller.chips[chip_idx]
    # Temporarily store chip configuration
    temp_filename = '.config_%s.json' % time.strftime('%Y_%m_%d_%H_%M_%S',time.localtime())
    print('temporarily storing previous configuration: %s' % temp_filename)
    chip.config.write(temp_filename,force=True)
    # Begin scan
    print('testing chip',chip.chip_id)
    controller.disable(chip_id=chip.chip_id)
    chip.config.global_threshold = threshold_max_coarse
    chip.config.reset_cycles = reset_cycles
    chip.config.enable_channels(channel_list)
    registers_to_write = [32] + [52,53,54,55] + [60,61,62]
    controller.write_configuration(chip, registers_to_write)
    print('clear buffer')
    controller.run(2,'clear buffer')
    # Check for noisy channels
    print('noise check')
    controller.run(run_time,'noise')
    packets_by_channel = {}
    for channel in channel_list:
        packets_by_channel[channel] = 0
    for packet in controller.reads[-1]:
        if packet.chipid == chip.chip_id:
            packets_by_channel[packet.channel_id] += 1
    noisy_channels = [channel for channel in packets_by_channel
                      if packets_by_channel[channel] >= saturation_level]
    print('channels at saturation: %s' % str(noisy_channels))
    print('disabling')
    chip.config.disable_channels(noisy_channels)
    controller.write_configuration(chip, [52,53,54,55])
    controller.run(1,'clear buffer')
    print('proceeding with scan')
    results = {}
    for channel in channel_list:
        results[channel] = {
            'threshold': [],
            'npackets': [],
            'adc_mean': [],
            'adc_rms': [],
            }
    break_flag = False
    final_threshold = {}
    threshold = threshold_max_coarse
    while threshold >= threshold_min_coarse:
        print('threshold %d' % threshold)
        chip.config.global_threshold = threshold
        controller.write_configuration(chip, 32)
        print('clear buffer (quick)')
        controller.run(0.1,'clear buffer')
        #if threshold == thresholds[0]:
        if len(controller.reads) > 0 and len(controller.reads[-1]) > 0:
        #if True:
            # Flush buffer for first cycle
            print('clear buffer (slow)')
            time.sleep(0.2)
            controller.run(2,'clear buffer')
            time.sleep(0.2)
        controller.reads = []
        # Collect data
        print('reading')
        controller.run(run_time,'scan threshold')
        print('done reading')
        # Process data
        packets = controller.reads[-1]
        adc_mean = 0
        adc_rms = 0
        if len(packets)>0:
            print('processing packets: %d' % len(packets))
            adcs_by_channel = {}
            adc_mean_by_channel = {}
            adc_rms_by_channel = {}
            for packet in controller.reads[-1]:
                if packet.chipid != chip.chip_id:
                    continue
                if not packet.channel_id in adcs_by_channel:
                    adcs_by_channel[packet.channel_id] = []
                adcs_by_channel[packet.channel_id] += [packet.dataword]
            for channel in channel_list:
                if channel in adcs_by_channel and len(adcs_by_channel[channel]) > 0:
                    adc_mean_by_channel[channel] = sum(adcs_by_channel[channel])/float(len(
                            adcs_by_channel[channel]))
                    adc_rms_by_channel[channel] = (sum([abs(adc-adc_mean_by_channel[channel])
                                                        for adc in adcs_by_channel[channel]])
                                                   / float(len(adcs_by_channel[channel])))
                    results[channel]['threshold'] += [threshold]
                    results[channel]['npackets'] += [len(adcs_by_channel[channel])]
                    results[channel]['adc_mean'] += [adc_mean_by_channel[channel]]
                    results[channel]['adc_rms'] += [adc_rms_by_channel[channel]]
                    print('%d %d %0.2f %.2f' % (channel, len(adcs_by_channel[channel]),
                                                adc_mean_by_channel[channel],
                                                adc_rms_by_channel[channel]))
                    if len(adcs_by_channel[channel]) >= saturation_level:
                        # Disable channel if saturation_level is hit
                        final_threshold[channel] = threshold
                        print('disable ch%d' % channel)
                        controller.disable(chip_id=chip.chip_id, channel_list=[channel])
            if all([channel in final_threshold.keys() or channel in noisy_channels
                    for channel in channel_list]):
                # All channel thresholds have been found - end scan
                break_flag = True
            # If no channels reached saturation, continue scan
            if not any([len(adcs_by_channel[channel]) >= saturation_level
                        for channel in adcs_by_channel.keys()]):
                threshold -= threshold_step_coarse
        else:
            threshold -= threshold_step_coarse
        if break_flag:
            break
    # Return chip to original state
    controller.disable(chip_id=chip.chip_id)
    chip.config.load(temp_filename)
    controller.write_configuration(chip)
    os.remove(temp_filename)
    if not controller.verify_configuration(chip_id=chip.chip_id)[0]:
        print('  warning: could not verify original chip state')
    if close_controller:
        controller.serial_close()
    print('summary (channel, threshold, npackets, adc mean, adc rms):')
    for channel in channel_list:
        if len(results[channel]['threshold']) > 0:
            print('%d %d %d %.2f %.2f' % (channel, results[channel]['threshold'][-1],
                                          results[channel]['npackets'][-1],
                                          results[channel]['adc_mean'][-1],
                                          results[channel]['adc_rms'][-1]))
        else:
            print('%d - - - -' % channel)
    print('channels with thresholds above %d: %s' % (threshold_max_coarse,
                                                     str(noisy_channels)))
    return results

def scan_threshold(controller=None, board='pcb-5', chip_idx=0,
                   channel_list=range(32), threshold_min_coarse=26,
                   threshold_max_coarse=37, threshold_step_coarse=1,
                   saturation_level=1000, run_time=0.1, reset_cycles=4092):
    '''Scan the signal rate versus channel threshold'''
    # Create controller and initialize chips to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        disable_chips(controller)
        print('  created controller')
    # Get chip under test
    chip = controller.chips[chip_idx]
    results = {}
    global_threshold_orig = chip.config.global_threshold
    channel_mask_orig = chip.config.channel_mask[:]
    print('testing chip',chip.chip_id)
    for channel in channel_list:
        print('testing channel',channel)
        # Configure chip for one channel operation
        chip.config.channel_mask = [1,]*32
        chip.config.pixel_trim_thresholds = [16]*32
        chip.config.channel_mask[channel] = 0
        chip.config.reset_cycles = reset_cycles
        print('  writing config')
        registers_to_write = range(32) + [52,53,54,55] + [60,61,62]
        controller.write_configuration(chip,registers_to_write)
        print('  reading config')
        controller.read_configuration(chip)
        print('  set mask')
        # Scan thresholds
        thresholds = range(threshold_min_coarse,
                           threshold_max_coarse+1,
                           threshold_step_coarse)
        # Scan from high to low
        thresholds.reverse()
        # Prepare to scan
        n_packets = []
        adc_means = []
        adc_rmss = []
        for threshold in thresholds:
            # Set global coarse threshold
            chip.config.global_threshold = threshold
            controller.write_configuration(chip,32)
            print('    set threshold')
            print('    clear buffer (quick)')
            controller.run(0.1,'clear buffer')
            del controller.reads[-1]
            #if threshold == thresholds[0]:
            if len(controller.reads) > 0 and len(controller.reads[-1]) > 0:
            #if True:
                # Flush buffer for first cycle
                print('    clear buffer (slow)')
                time.sleep(0.2)
                controller.run(2,'clear buffer')
                time.sleep(0.2)
            controller.reads = []
            # Collect data
            print('    reading')
            controller.run(run_time,'scan threshold')
            print('    done reading')
            # Process data
            packets = controller.reads[-1]
            adc_mean = 0
            adc_rms = 0
            if len(packets)>0:
                print('    processing packets: %d' % len(packets))
                adcs = [p.dataword for p in packets
                        if p.chipid == chip.chip_id and p.channel_id == channel]
                if len(adcs) > 0:
                    adc_mean = sum(adcs)/float(len(adcs))
                    adc_rms = (sum([abs(adc-adc_mean) for adc in adcs])
                               / float(len(adcs)))
            n_packets.append(len(packets))
            adc_means.append(adc_mean)
            adc_rmss.append(adc_rms)
            print(    '%d %d %0.2f %0.4f' % (threshold, len(packets),
                                             adc_mean, adc_rms))
            if len(packets)>=saturation_level:
                # Stop scanning if saturation level is hit.
                break
        results[channel] = [thresholds[:], n_packets[:],
                            adc_means[:], adc_rmss[:]]

    print('Summary (last threshold, npackets, adc mean, adc rms)')
    for channel in results:
        print('%d %d %d %.2f %.2f' % (channel, results[channel][0][-1],
                                      results[channel][1][-1], results[channel][2][-1],
                                      results[channel][3][-1]))
    # Restore original global threshold and channel mask
    chip.config.global_threshold = global_threshold_orig
    chip.config.pixel_trim_thresholds = [16]*32
    controller.write_configuration(chip,32)
    controller.write_configuration(chip,range(32))
    chip.config.channel_mask = channel_mask_orig
    controller.write_configuration(chip,[52,53,54,55])
    if close_controller:
        controller.serial_close()
    return results

def scan_threshold_with_communication(controller=None, board='pcb-1', chip_idx=0,
                                      channel_list=range(32), threshold_min_coarse=26,
                                      threshold_max_coarse=37, threshold_step_coarse=1,
                                      saturation_level=1000, run_time=0.1):
    '''Scan the signal rate versus channel threshold while writing to chip registers'''
    # Create controller and initialize chips to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        disable_chips(controller)
        print('  created controller')
    # Get chip under test
    chip = controller.chips[chip_idx]
    results = {}
    global_threshold_orig = chip.config.global_threshold
    channel_mask_orig = chip.config.channel_mask[:]
    print('testing chip',chip.chip_id)
    for channel in channel_list:
        print('testing channel',channel)
        # Configure chip for one channel operation
        chip.config.channel_mask = [1,]*32
        chip.config.channel_mask[channel] = 0
        print('  writing config')
        controller.write_configuration(chip,[52,53,54,55])
        print('  reading config')
        controller.read_configuration(chip)
        print('  set mask')
        # Scan thresholds
        thresholds = range(threshold_min_coarse,
                           threshold_max_coarse+1,
                           threshold_step_coarse)
        # Scan from high to low
        thresholds.reverse()
        # Prepare to scan
        n_packets = []
        adc_means = []
        adc_rmss = []
        for threshold in thresholds:
            # Set global coarse threshold
            chip.config.global_threshold = threshold
            controller.write_configuration(chip,32)
            print('    set threshold')
            print('    clear buffer (quick)')
            controller.run(0.1,'clear buffer')
            del controller.reads[-1]
            #if threshold == thresholds[0]:
            if len(controller.reads) > 0 and len(controller.reads[-1]) > 0:
            #if True:
                # Flush buffer for first cycle
                print('    clear buffer (slow)')
                time.sleep(0.2)
                controller.run(2,'clear buffer')
                time.sleep(0.2)
            controller.reads = []
            # Collect data
            print('    writing and reading')
            controller.write_configuration(chip,32,write_read=run_time)
            print('    done reading')
            # Process data
            packets = controller.reads[-1]
            adc_mean = 0
            adc_rms = 0
            if len(packets)>0:
                print('    processing packets: %d' % len(packets))
                adcs = [p.dataword for p in packets
                        if p.chipid == chip.chip_id and p.channel_id == channel]
                if len(adcs) > 0:
                    adc_mean = sum(adcs)/float(len(adcs))
                    adc_rms = (sum([abs(adc-adc_mean) for adc in adcs])
                               / float(len(adcs)))
            n_packets.append(len(packets))
            adc_means.append(adc_mean)
            adc_rmss.append(adc_rms)
            print(    '%d %d %0.2f %0.4f' % (threshold, len(packets),
                                             adc_mean, adc_rms))
            if len(packets)>=saturation_level:
                # Stop scanning if saturation level is hit.
                break
        results[channel] = [thresholds[:], n_packets[:],
                            adc_means[:], adc_rmss[:]]
    print('Summary (last threshold, npackets, adc mean, adc rms)')
    for channel in results:
        print('%d %d %d %.2f %.2f' % (channel, results[channel][0][-1],
                                      results[channel][1][-1], results[channel][2][-1],
                                      results[channel][3][-1]))
    # Restore original global threshold and channel mask
    chip.config.global_threshold = global_threshold_orig
    controller.write_configuration(chip,32)
    chip.config.channel_mask = channel_mask_orig
    controller.write_configuration(chip,[52,53,54,55])
    if close_controller:
        controller.serial_close()
    return results

def test_csa_gain(controller=None, chip_idx=0, board='pcb-5', reset_cycles=4096,
                  global_threshold=40, pixel_trim_thresholds=[16]*32, pulse_dac_start=1,
                  pulse_dac_end=60, pulse_dac_step=5, n_pulses=10, adc_burst_length=0,
                  channel_list=range(32), dac_max=255, dac_min=0, csa_recovery_time=0.1,
                  sample_cycles=255):
    '''Pulse channels with increasing pulse sizes'''
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        controller.disable()
    chip = controller.chips[chip_idx]
    print('initial config for chip %d' % chip.chip_id)
    # Save current configuration
    temp_filename = 'tmp_config.json'
    chip.config.write(temp_filename,force=True)
    # Set up chip for testing
    controller.disable(chip_id=chip.chip_id)
    chip.config.global_threshold = global_threshold
    for idx, channel in enumerate(channel_list):
        chip.config.pixel_trim_thresholds[channel] = pixel_trim_thresholds[idx]
    chip.config.reset_cycles = reset_cycles
    chip.config.adc_burst_length = adc_burst_length
    chip.config.sample_cycles = sample_cycles
    controller.write_configuration(chip, range(33) + [48] + range(60,63))
    controller.run(1,'clear buffer')
    if not controller.verify_configuration(chip_id=chip.chip_id)[0]:
        print('Warning: chip config does not match readback')
    # Pulse chip,channel
    #for channel in channel_list:
    controller.disable(chip_id=chip.chip_id)
    controller.enable(chip_id=chip.chip_id, channel_list=channel_list)
    controller.disable_testpulse(chip_id=chip.chip_id)
    controller.enable_testpulse(chip_id=chip.chip_id, channel_list=channel_list,
                                start_dac=dac_max)
    time.sleep(csa_recovery_time)
    # Check noise rate
    print('checking noise rate (c%d):'%(chip.chip_id))
    controller.run(1,'noise rate')
    print('%d Hz' % len(controller.reads[-1]))
    for pulse_dac in range(pulse_dac_start, pulse_dac_end + pulse_dac_step, pulse_dac_step):
        print('DAC pulse: %d, pulsing' % pulse_dac)
        print('reset DAC')
        controller.enable_testpulse(chip_id=chip.chip_id, channel_list=channel_list,
                                    start_dac=dac_max)
        time.sleep(csa_recovery_time)
        controller.run(1,'clear buffer')
        reset_attempts = 0
        pulses_sent = 0
        packets_received = 0
        while pulses_sent < n_pulses and reset_attempts < 2:
            try:
                controller.issue_testpulse(chip_id=chip.chip_id, pulse_dac=pulse_dac,
                                           min_dac=dac_min)
                time.sleep(csa_recovery_time)
                reset_attempts = 0
                pulses_sent += 1
                packets_received += len(controller.reads[-1])
            except ValueError:
                print('reset DAC')
                controller.enable_testpulse(chip_id=chip.chip_id, channel_list=channel_list,
                                            start_dac=dac_max)
                time.sleep(csa_recovery_time)
                controller.run(1,'clear buffer')
                reset_attempts += 1
        if reset_attempts >= 2:
            print('testpulse reset failed - check pulse size and DAC min/max')
        print('%d sent / %d received' % (pulses_sent, packets_received))
    # Restore previous state
    controller.disable(chip_id=chip.chip_id)
    chip.config.load(temp_filename)
    controller.write_configuration(chip)
    os.remove(temp_filename)
    if not controller.verify_configuration(chip_id=chip.chip_id)[0]:
        print('Warning: Could not restore chip state')
    if close_controller:
        controller.serial_close()

def test_testpulse_linearity(controller=None, chip_idx=0, board='pcb-5', reset_cycles=4096,
                             global_threshold=40, pixel_trim_thresholds=[16]*32,
                             pulse_dac=50, dac_max=255, dac_min=0, dac_step=1,
                             n_pulses=1, adc_burst_length=0, channel_list=range(32),
                             csa_recovery_time=0.1, sample_cycles=255):
    '''Pulse channels with same pulse size changing the DAC step values'''
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        controller.disable()
    chip = controller.chips[chip_idx]
    print('initial config for chip %d' % chip.chip_id)
    # Save current configuration
    temp_filename = 'tmp_config.json'
    chip.config.write(temp_filename,force=True)
    # Set up chip for testing
    controller.disable(chip_id=chip.chip_id)
    chip.config.global_threshold = global_threshold
    for idx, channel in enumerate(channel_list):
        chip.config.pixel_trim_thresholds[channel] = pixel_trim_thresholds[idx]
    chip.config.reset_cycles = reset_cycles
    chip.config.adc_burst_length = adc_burst_length
    chip.config.sample_cycles = sample_cycles
    controller.write_configuration(chip, range(33) + [48] + range(60,63))
    controller.run(1,'clear buffer')
    if not controller.verify_configuration(chip_id=chip.chip_id)[0]:
        print('Warning: chip config does not match readback')
    # Pulse chip,channel
    #for channel in channel_list:
    controller.disable(chip_id=chip.chip_id)
    controller.enable(chip_id=chip.chip_id, channel_list=channel_list)
    controller.disable_testpulse(chip_id=chip.chip_id)
    controller.enable_testpulse(chip_id=chip.chip_id, channel_list=channel_list,
                                start_dac=dac_max)
    time.sleep(csa_recovery_time)
    # Check noise rate
    print('checking noise rate (c%d):'%(chip.chip_id))
    controller.run(1,'noise rate')
    print('%d Hz' % len(controller.reads[-1]))
    for dac_value in range(dac_max, dac_min - 1, -dac_step):
        print('DAC pulse: %d - %d, pulsing' % (dac_value, dac_value-pulse_dac))
        print('reset DAC')
        controller.enable_testpulse(chip_id=chip.chip_id, channel_list=channel_list,
                                    start_dac=dac_value)
        time.sleep(csa_recovery_time)
        controller.run(1,'clear buffer')
        reset_attempts = 0
        pulses_sent = 0
        packets_received = 0
        while pulses_sent < n_pulses and reset_attempts < 2:
            try:
                controller.issue_testpulse(chip_id=chip.chip_id, pulse_dac=pulse_dac,
                                           min_dac=dac_value-pulse_dac)
                time.sleep(csa_recovery_time)
                reset_attempts = 0
                pulses_sent += 1
                packets_received += len(controller.reads[-1])
            except ValueError:
                print('reset DAC')
                controller.enable_testpulse(chip_id=chip.chip_id, channel_list=channel_list,
                                            start_dac=dac_value)
                time.sleep(csa_recovery_time)
                controller.run(1,'clear buffer')
                reset_attempts += 1
        if reset_attempts >= 2:
            print('testpulse reset failed - check pulse size and DAC min/max')
        print('%d sent / %d received' % (pulses_sent, packets_received))
    # Restore previous state
    controller.disable(chip_id=chip.chip_id)
    chip.config.load(temp_filename)
    controller.write_configuration(chip)
    os.remove(temp_filename)
    if not controller.verify_configuration(chip_id=chip.chip_id)[0]:
        print('Warning: Could not restore chip state')
    if close_controller:
        controller.serial_close()

def test_leakage_current(controller=None, chip_idx=0, board='pcb-5', reset_cycles=None,
                         global_threshold=125, trim=16, run_time=1, channel_list=range(32)):
    '''Sets chips to high threshold and counts number of triggers'''
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)

    chip = controller.chips[chip_idx]
    print('initial configuration for chip %d' % chip.chip_id)
    temp_filename = 'tmp_config.json'
    chip.config.write(temp_filename,force=True)
    chip.config.global_threshold = global_threshold
    chip.config.pixel_trim_thresholds = [trim] * 32
    if reset_cycles is None:
        chip.config.periodic_reset = 0
    else:
        chip.config.reset_cycles = reset_cycles
        chip.config.periodic_reset = 1
    chip.config.disable_channels()
    controller.write_configuration(chip)

    return_data = {
        'channel':[],
        'n_packets':[],
        'run_time':[],
        'rate': [],
        }
    print('clear buffer')
    controller.run(2,'clear buffer')
    del controller.reads[-1]
    for channel in channel_list:
        chip.config.disable_channels()
        chip.config.enable_channels([channel])
        controller.write_configuration(chip,range(52,56))
        # flush buffer
        print('clear buffer')
        controller.run(0.1,'clear buffer')
        del controller.reads[-1]
        # run for run_time
        print('begin test (runtime = %.1f, channel = %d)' % (run_time, channel))
        controller.run(run_time,'leakage current test')
        read = controller.reads[-1]
        return_data['channel'] += [channel]
        return_data['n_packets'] += [len(read)]
        return_data['run_time'] += [run_time]
        return_data['rate'] += [float(len(read))/run_time]
        print('channel %2d: %.2f' % (channel, return_data['rate'][-1]))
    mean_rate = sum(return_data['rate'])/len(return_data['rate'])
    rms_rate = sum(abs(rate - mean_rate)
                   for rate in return_data['rate'])/len(return_data['rate'])
    print('chip mean: %.3f, rms: %.3f' % (mean_rate, rms_rate))
    controller.disable(chip_id=chip.chip_id)
    chip.config.load(temp_filename)
    controller.write_configuration(chip)
    os.remove(temp_filename)
    if close_controller:
        controller.serial_close()
    return return_data

def pulse_chip(controller, chip, dac_level):
    '''Issue one pulse to specific chip'''
    chip.config.csa_testpulse_dac_amplitude = dac_level
    controller.write_configuration(chip,46,write_read=0.1)
    return controller.reads[-1]

def noise_test_all_chips(n_pulses=1000, pulse_channel=0, pulse_dac=6, threshold=40,
                         controller=None, testpulse_dac_max=235, testpulse_dac_min=40,
                         trim=0, board='pcb-5', reset_cycles=4096, csa_recovery_time=0.1,
                         reset_dac_time=1):
    '''Run noise_test_internal_pulser on all available chips'''
    # Create controller and initialize chip,s to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)

    for chip_idx in range(len(controller.chips)):
        chip_threshold = threshold
        chip_pulse_dac = pulse_dac
        if isinstance(threshold, list):
            chip_threshold = threshold[chip_idx]
        if isinstance(pulse_dac, list):
            chip_pulse_dac = pulse_dac[chip_idx]
        noise_test_internal_pulser(board=board, chip_idx=chip_idx, n_pulses=n_pulses,
                                   pulse_channel=pulse_channel, reset_cycles=reset_cycles,
                                   pulse_dac=chip_pulse_dac, threshold=chip_threshold,
                                   controller=controller, csa_recovery_time=csa_recovery_time,
                                   testpulse_dac_max=testpulse_dac_max,
                                   reset_dac_time=reset_dac_time,
                                   testpulse_dac_min=testpulse_dac_min, trim=trim)
    result = controller.reads
    if close_controller:
        controller.serial_close()
    return result

def noise_test_external_pulser(board='pcb-5', chip_idx=0, run_time=10,
                               channel_list=range(32), global_threshold=200,
                               controller=None, reset_cycles=4096):
    '''Scan through channels with external trigger enabled - report adc width'''
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
    disable_chips(controller)
    # Get chip under test
    chip = controller.chips[chip_idx]
    print('initial configuration for chip %d' % chip.chip_id)
    chip.config.global_threshold = global_threshold
    chip.config.reset_cycles = reset_cycles
    controller.write_configuration(chip,32)
    controller.write_configuration(chip,[60,61,62])
    adc_values = {}
    mean = {}
    std_dev = {}
    for channel in channel_list:
        print('test channel %d' % channel)
        print('  clear buffer (slow)')
        controller.run(1,'clear buffer')
        chip.config.disable_channels()
        chip.config.enable_channels([channel])
        chip.config.disable_external_trigger()
        chip.config.enable_external_trigger([channel])
        controller.write_configuration(chip,range(52,60))
        print('  clear buffer (quick)')
        controller.run(0.1,'clear buffer')
        print('  run')
        controller.run(run_time,'collect data')
        adc_values[channel] = [packet.dataword for packet in controller.reads[-1]
                               if packet.packet_type == packet.DATA_PACKET and
                               packet.chipid == chip.chip_id and
                               packet.channel_id == channel]
        chip.config.disable_channels()
        chip.config.disable_external_trigger()
        controller.write_configuration(chip,range(52,60))
        if len(adc_values[channel]) > 0:
            mean[channel] = float(sum(adc_values[channel]))/len(adc_values[channel])
            std_dev[channel] = math.sqrt(sum([float(value)**2 for value in adc_values[channel]])/len(adc_values[channel]) - mean[channel]**2)
            print('%d  %f  %f' % (channel, mean[channel], std_dev[channel]))
    print('summary (channel, mean, std dev):')
    for channel in channel_list:
        if channel in mean:
            print('%d  %f  %f' % (channel, mean[channel], std_dev[channel]))

    flush_logger()
    if close_controller:
        controller.serial_close()
    return (adc_values, mean, std_dev)

def noise_test_low_threshold(board='pcb-5', chip_idx=0, run_time=1,
                             channel_list=range(32), global_threshold=0,
                             controller=None):
    '''Scan through channels at low threshold - report adc width'''
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
    disable_chips(controller)
    # Get chip under test
    chip = controller.chips[chip_idx]
    print('initial configuration for chip %d' % chip.chip_id)
    chip.config.global_threshold = global_threshold
    controller.write_configuration(chip,32)
    adc_values = {}
    mean = {}
    std_dev = {}
    for channel in channel_list:
        print('test channel %d' % channel)
        print('clear buffer (slow)')
        controller.run(1,'clear buffer')
        chip.config.enable_channels([channel])
        controller.write_configuration(chip,range(52,56))
        print('clear buffer (quick)')
        controller.run(0.1,'clear buffer')
        controller.run(run_time,'collect data')
        adc_values[channel] = [packet.dataword for packet in controller.reads[-1]
                               if packet.packet_type == packet.DATA_PACKET and
                               packet.chipid == chip.chip_id and
                               packet.channel_id == channel]
        chip.config.disable_channels()
        controller.write_configuration(chip,range(52,56))
        if len(adc_values[channel]) > 0:
            mean[channel] = float(sum(adc_values[channel]))/len(adc_values[channel])
            std_dev[channel] = math.sqrt(sum([float(value)**2 for value in adc_values[channel]])/len(adc_values[channel]) - mean[channel]**2)
            print('%d  %f  %f' % (channel, mean[channel], std_dev[channel]))
    print('summary (channel, mean, std dev):')
    for channel in channel_list:
        if channel in mean.keys():
            print('%d  %f  %f' % (channel, mean[channel], std_dev[channel]))

    flush_logger()
    if close_controller:
        controller.serial_close()
    return (adc_values, mean, std_dev)

def noise_test_internal_pulser(board='pcb-5', chip_idx=0, n_pulses=1000,
                               pulse_channel=0, pulse_dac=6, threshold=40,
                               controller=None, testpulse_dac_max=235,
                               testpulse_dac_min=40, trim=0, reset_cycles=4096,
                               csa_recovery_time=0.1, reset_dac_time=1):
    '''Use cross-trigger from one channel to evaluate noise on other channels'''
    # Create controller and initialize chips to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        #disable_chips(controller)
    # Get chip under test
    chip = controller.chips[chip_idx]
    print('initial configuration for chip %d' % chip.chip_id)
    # Configure chip for pulsing one channel
    chip.config.csa_testpulse_enable[pulse_channel] = 0 # Connect
    controller.write_configuration(chip,[42,43,44,45])
    # Initialize DAC level, and issuing cross-triggers
    chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
    controller.write_configuration(chip,46)
    # Set initial threshold, and enable cross-triggers
    chip.config.global_threshold = threshold
    chip.config.pixel_trim_thresholds = [31] * 32
    chip.config.pixel_trim_thresholds[pulse_channel] = trim
    chip.config.cross_trigger_mode = 1
    chip.config.reset_cycles = reset_cycles
    controller.write_configuration(chip,range(60,63)) # reset cycles
    controller.write_configuration(chip,range(32)) # trim
    controller.write_configuration(chip,[32,47]) # global threshold / xtrig
    #chip.config.enable_analog_monitor(pulse_channel)
    #controller.write_configuration(chip,range(38,42)) # monitor
    #chip.config.enable_channels([pulse_channel]) # enable pulse channel
    #controller.write_configuration(chip,range(52,56)) # channel mask
    print('initial configuration done')
    # Pulse chip n times
    dac_level = testpulse_dac_max
    lost = 0
    extra = 0
    print('clear buffer')
    controller.run(0.1, 'clear buffer')
    del controller.reads[-1]
    time.sleep(csa_recovery_time)
    for pulse_idx in range(n_pulses):
        if dac_level < (testpulse_dac_min + pulse_dac):
            # Reset DAC level if it is too low to issue pulse
            chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
            controller.write_configuration(chip,46)
            time.sleep(reset_dac_time) # Wait for front-end to settle
            print('reset DAC value')
            # FIXME: do we need to flush buffer here?
            dac_level = testpulse_dac_max
        # Issue pulse
        dac_level -= pulse_dac  # Negative DAC step mimics electron arrival
        time.sleep(csa_recovery_time)
        result = pulse_chip(controller, chip, dac_level)
        if len(result) - 32 > 0:
            extra += 1
        elif len(result) - 32 < 0:
            lost += 1
        print('pulse: %4d, received: %4d, DAC: %4d' % (pulse_idx, len(result), dac_level))

    # Reset DAC level, and disconnect channel
    chip.config.disable_testpulse() # Disconnect
    controller.write_configuration(chip,[42,43,44,45]) # testpulse
    chip.config.csa_testpulse_dac_amplitude = 0
    controller.write_configuration(chip,46) # dac amplitude
    chip.config.cross_trigger_mode = 0
    chip.config.global_threshold = 255
    controller.write_configuration(chip,[32,47]) # global threshold / xtrig
    chip.config.pixel_trim_thresholds = [16] * 32
    controller.write_configuration(chip,range(32)) # trim
    #chip.config.disable_analog_monitor()
    #controller.write_configuration(chip,range(38,42)) # monitor

    # Keep a handle to chip data, and return
    result = controller.reads
    flush_logger()
    if close_controller:
        controller.serial_close()
    print('Pulses with # trigs > 1: %4d, Missed trigs: %4d' % (extra, lost))
    return result

def scan_threshold_with_pulse(controller=None, board='pcb-1', chip_idx=0,
                              channel_list=range(32), max_acceptable_efficiency=1.5,
                              min_acceptable_efficiency=0.5, n_pulses=100, dac_pulse=6,
                              testpulse_dac_max=235, testpulse_dac_min=229, reset_cycles=4096,
                              threshold_max=40, threshold_min=20, threshold_step=1):
    ''' Pulse channels with test pulse to determine the minimum threshold for
    triggering at least a specified efficiency '''
    close_controller = False
    if not controller:
        # Create controller and initialize chips to appropriate state
        close_controller = True
        controller = quickcontroller(board)
        disable_chips(controller)
    chip = controller.chips[chip_idx]
    controller.run(5, 'clear buffer')
    results = {}
    for channel_idx, channel in enumerate(channel_list):
        print('configuring chip %d channel %d' % (chip.chip_id, channel))
        # Configure chip for pulsing one channel
        chip.config.csa_testpulse_enable = [1]*32 # Disconnect any channels
        chip.config.csa_testpulse_enable[channel] = 0 # Connect
        controller.write_configuration(chip,[42,43,44,45])
        # Initialize DAC level
        chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
        controller.write_configuration(chip,46)
        # Enable channel
        chip.config.disable_channels()
        chip.config.enable_channels([channel])
        controller.write_configuration(chip,[52,53,54,55])
        controller.run(5, 'clear buffer')
        thresholds = []
        efficiencies = []
        for threshold in range(threshold_max, threshold_min-1, -threshold_step):
            # Set threshold and trim
            print('  threshold %d' % threshold)
            chip.config.global_threshold = threshold
            chip.config.reset_cycles = reset_cycles
            controller.write_configuration(chip,range(60,63)) # reset cycles
            controller.write_configuration(chip,[32,47]) # global threshold / xtrig
            controller.run(0.1, 'clear buffer')
            pulses_issued = 0
            triggers_received = 0
            dac_level = testpulse_dac_max
            print('  pulsing')
            for pulse_idx in range(n_pulses):
                if dac_level < (testpulse_dac_min + dac_pulse):
                    # Reset DAC level if it is too low to issue pulse
                    chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
                    controller.write_configuration(chip,46)
                    time.sleep(0.1) # Wait for front-end to settle
                    controller.run(0.1, 'clear buffer')
                    dac_level = testpulse_dac_max
                # Issue pulse
                dac_level -= dac_pulse  # Negative DAC step mimics electron arrival
                result = pulse_chip(controller, chip, dac_level)
                pulses_issued += 1
                triggers_received += len(result)
            print('  pulses issued: %d, triggers received: %d' % (pulses_issued,
                                                                  triggers_received))
            efficiency = float(triggers_received)/pulses_issued
            thresholds.append(threshold)
            efficiencies.append(efficiency)
            if efficiency < min_acceptable_efficiency:
                continue
            else:
                if efficiency > max_acceptable_efficiency:
                    print('outside of max acceptable_efficiency')
                print('%d %d %d %d %.2f' % (channel, threshold, pulses_issued,
                                            triggers_received,
                                            float(triggers_received)/pulses_issued))
                results[channel] = {'thresholds' : thresholds,
                                    'efficiencies': efficiencies}
                break

    print('summary')
    print('  channel, lowest threshold reached, efficiency')
    for key in results:
        if isinstance(key, int):
            print('%d %d %.2f'% (key,results[key]['thresholds'][-1],
                                 results[key]['efficiencies'][-1]))

    if close_controller:
        controller.serial_close()
    return results

def scan_trim_with_pulse(controller=None, board='pcb-1', chip_idx=0,
                         channel_list=range(32), max_acceptable_efficiency=1.5,
                         min_acceptable_efficiency=0.5, n_pulses=100, dac_pulse=6,
                         testpulse_dac_max=235, testpulse_dac_min=229, reset_cycles=4096,
                         trim_max=31, trim_min=0, trim_step=1, threshold=40):
    ''' Pulse channels with test pulse to determine the minimum trim for
    triggering at least a specified efficiency '''
    close_controller = False
    if not controller:
        # Create controller and initialize chips to appropriate state
        close_controller = True
        controller = quickcontroller(board)
        disable_chips(controller)
    chip = controller.chips[chip_idx]
    controller.run(5, 'clear buffer')
    results = {}
    for channel_idx, channel in enumerate(channel_list):
        print('configuring chip %d channel %d' % (chip.chip_id, channel))
        # Configure chip for pulsing one channel
        chip.config.csa_testpulse_enable = [1]*32 # Disconnect any channels
        chip.config.csa_testpulse_enable[channel] = 0 # Connect
        controller.write_configuration(chip,[42,43,44,45])
        # Initialize DAC level
        chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
        controller.write_configuration(chip,46)
        # Enable channel
        chip.config.disable_channels()
        chip.config.enable_channels([channel])
        controller.write_configuration(chip,[52,53,54,55])
        # Set threshold
        chip.config.global_threshold = threshold
        controller.write_configuration(chip,[32])
        controller.run(5, 'clear buffer')
        trims = []
        efficiencies = []
        for trim in range(trim_max, trim_min-1, -trim_step):
            # Set threshold and trim
            print('  trim %d' % trim)
            chip.config.pixel_trim_thresholds[channel] = trim
            chip.config.reset_cycles = reset_cycles
            controller.write_configuration(chip,range(32)) # trim
            controller.write_configuration(chip,range(60,63)) # reset cycles
            controller.write_configuration(chip,[32,47]) # global threshold / xtrig
            controller.run(0.1, 'clear buffer')
            pulses_issued = 0
            triggers_received = 0
            dac_level = testpulse_dac_max
            print('  pulsing')
            for pulse_idx in range(n_pulses):
                if dac_level < (testpulse_dac_min + dac_pulse):
                    # Reset DAC level if it is too low to issue pulse
                    chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
                    controller.write_configuration(chip,46)
                    time.sleep(0.1) # Wait for front-end to settle
                    controller.run(0.1, 'clear buffer')
                    dac_level = testpulse_dac_max
                # Issue pulse
                dac_level -= dac_pulse  # Negative DAC step mimics electron arrival
                result = pulse_chip(controller, chip, dac_level)
                pulses_issued += 1
                triggers_received += len(result)
            print('  pulses issued: %d, triggers received: %d' % (pulses_issued,
                                                                  triggers_received))
            efficiency = float(triggers_received)/pulses_issued
            trims.append(trim)
            efficiencies.append(efficiency)
            if efficiency < min_acceptable_efficiency and not trim == trim_min:
                continue
            else:
                if efficiency > max_acceptable_efficiency:
                    print('outside of max acceptable_efficiency')
                print('%d %d %d %d %.2f' % (channel, trim, pulses_issued,
                                            triggers_received,
                                            float(triggers_received)/pulses_issued))
                results[channel] = {'trims' : trims,
                                    'efficiencies': efficiencies}
                break

    print('summary')
    print('  channel, lowest trim reached, efficiency')
    for key in results:
        if isinstance(key, int):
            print('  %d %d %.2f' % (key, results[key]['trims'][-1],
                                    results[key]['efficiencies'][-1]))

    if close_controller:
        controller.serial_close()
    return results

def test_min_signal_amplitude(controller=None, board='pcb-1', chip_idx=0,
                              channel_list=range(32), threshold=40, trim=[16]*32,
                              threshold_trigger_rate=0.9, n_pulses=100, min_dac_amp=1,
                              max_dac_amp=20, dac_step=1, testpulse_dac_max=235,
                              testpulse_dac_min=40, reset_cycles=4096):
    ''' Pulse channel with increasing pulse sizes to determine the minimum pulse size for
    triggering at >90% '''
    close_controller = False
    if not controller:
        # Create controller and initialize chips to appropriate state
        close_controller = True
        controller = quickcontroller(board)
        disable_chips(controller)
    chip = controller.chips[chip_idx]
    results = {'channels_'}
    for channel_idx, channel in enumerate(channel_list):
        print('configuring for chip %d channel %d' % (chip.chip_id, channel))
        # Configure chip for pulsing one channel
        chip.config.csa_testpulse_enable[channel] = 0 # Connect
        controller.write_configuration(chip,[42,43,44,45])
        # Initialize DAC level, and issuing cross-triggers
        chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
        controller.write_configuration(chip,46)
        # Set threshold and trim
        chip.config.global_threshold = threshold
        chip.config.pixel_trim_thresholds[channel_idx] = trim[channel_idx]
        chip.config.reset_cycles = reset_cycles
        controller.write_configuration(chip,range(60,63)) # reset cycles
        controller.write_configuration(chip,range(32)) # trim
        controller.write_configuration(chip,[32,47]) # global threshold / xtrig
        for dac_amp in range(min_dac_amp, max_dac_amp+1, dac_step):
            # Step over a range of dac_amplitudes
            print('  pulse amp: %d' % dac_amp)
            dac_level = max_dac_amp
            controller.run(0.1, 'clear buffer')
            del controller.reads[-1]
            pulses_issued = 0
            triggers_received = 0
            for pulse_idx in range(n_pulses):
                if dac_level < (testpulse_dac_min + pulse_dac):
                    # Reset DAC level if it is too low to issue pulse
                    chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
                    controller.write_configuration(chip,46)
                    time.sleep(reset_dac_time) # Wait for front-end to settle
                    controller.run(0.1, 'clear buffer')
                    del controller.reads[-1]
                    dac_level = testpulse_dac_max
                # Issue pulse
                dac_level -= dac_amp  # Negative DAC step mimics electron arrival
                result = pulse_chip(controller, chip, dac_level)
                pulses_issued += 1
                triggers_received += len(result)
            print('pulses issued: %d, triggers received: %d' % (pulses_issued,
                                                                triggers_received))

    if close_controller:
        controller.serial_close()
    return

def analog_monitor(controller=None, board='pcb-5', chip_idx=0, channel=0):
    '''Connect analog monitor for this channel'''
    close_controller = False
    if not controller:
        # Create controller and initialize chips to appropriate state
        close_controller = True
        controller = quickcontroller(board)
    # Get chip under test
    chip = controller.chips[chip_idx]
    # Configure chip for analog monitoring
    chip.config.csa_monitor_select = [0,]*32
    chip.config.csa_monitor_select[channel] = 1
    controller.write_configuration(chip, [38,39,40,41])
    # return controller, for optional reuse
    if close_controller:
        controller.serial_close()
    return controller

def examine_global_scan(coarse_data, saturation_level=1000):
    '''Examine coarse threshold scan results, and determine optimum threshold'''
    result = {}
    sat_threshes = []
    chan_level_too_high = []
    chan_level_too_low = []
    for (channel_num, data) in coarse_data.iteritems():
        thresholds = data[0]
        npackets = data[1]
        adc_widths = data[3]
        saturation_thresh = -1
        saturation_npacket = -1
        # Only process if not already saturated
        if npackets[0] >= saturation_level:
            chan_level_too_high.append(channel_num)
            continue
        if npackets[-1] < saturation_level:
            chan_level_too_low.append(channel_num)
            continue
        for (thresh, npacket, adc_width) in zip(thresholds, npackets, adc_widths):
            if npacket >= saturation_level:
                saturation_thresh = thresh
                saturation_npacket = npacket
                saturation_adc_width = adc_width
                sat_threshes.append(saturation_thresh)
                break
        result[channel_num] = {'saturation_thresh_global':saturation_thresh,
                               'saturation_npacket':saturation_npacket,
                               'saturation_adc_width':saturation_adc_width}
    # Collect other relevant results
    result['chan_level_too_high'] = chan_level_too_high
    result['chan_level_too_low'] = chan_level_too_low
    result['mean_thresh'] = sum(sat_threshes)/float(len(sat_threshes))
    return result

def examine_fine_scan(fine_data, saturation_level=1000):
    '''Examine fine threshold scan results, and determine optimum threshold'''
    result = {}
    sat_trims = []
    chan_level_too_high = []
    chan_level_too_low = []
    print fine_data
    for channel_num in fine_data.keys():
        print fine_data[0]
        trims = fine_data[channel_num]['trims']
        npackets = fine_data[channel_num]['npackes']
        #adc_widths = data['']
        saturation_trim = -1
        saturation_npacket = -1
        # Only process if not already saturated
        if npackets[0] > saturation_level:
            chan_level_too_high.append(channel_num)
            continue
        if npackets[-1] <= saturation_level:
            chan_level_too_low.append(channel_num)
            continue
        for (trim, npacket) in zip(trims, npackets):
            if npacket > saturation_level:
                saturation_trim = trim
                saturation_npacket = npacket
                #saturation_adc_width = adc_width
                sat_trims.append(saturation_trim)
                break
        result[channel_num] = {'saturation_trim':saturation_trim,
                               'saturation_npacket':saturation_npacket}
                               #'saturation_adc_width':saturation_adc_width}
    # Collect other relevant results
    result['chan_level_too_high'] = chan_level_too_high
    result['chan_level_too_low'] = chan_level_too_low
    return result

def run_threshold_test():
    # Run test
    cont = quickcontroller()
    disable_chips(cont)
    chip_results = []
    for chipidx in range(len(cont.chips)):
        print('%%%%%%%%%% Scanning chip: %d %%%%%%%%%%%%' % chipidx)
        chip_result = scan_threshold(controller=cont, chip_idx=chipidx)
        chip_results.append(chip_result)
    thresh_descs = []
    for chipidx in range(len(cont.chips)):
        thresh_desc = examine_global_scan(chip_results[chipidx])
        thresh_descs.append(thresh_desc)
    print('Mean Thresholds:')
    for chipidx in range(len(cont.chips)):
        ch_result = thresh_descs[chipidx]
        print('  Chip %d: %f' % (chipidx,ch_result['mean_thresh']))
    print('Out of range channels:')
    for chipidx in range(len(cont.chips)):
        ch_result = thresh_descs[chipidx]
        print('  Chip %d (high,low): %r, %r' % (
            chipidx,
            ch_result['chan_level_too_high'],
            ch_result['chan_level_too_low']))
    cont.serial_close()
    return (thresh_descs, chip_results)

def load_standard_test_configuration(path=None):
    if path is None:
        path = '.'
    with open(path + '/standard_test_configuration.json','r') as fi:
        test_config = json.load(fi)
    return test_config

def run_standard_tests(path=None):
    test_config = load_standard_test_configuration(path)
    results = {}
    for test in test_config:
        test_handle = None
        test_result = None
        if test['handle'] in globals():
            test_handle = globals()[test['handle']]
        if not test_handle is None:
            try:
                print('-'*10 + ' %s '% test['handle'] + '-'*10)
                print('%s(' % test['handle'])
                args = test['args']
                for arg in args:
                    print('    %s = %s,' % (arg, str(args[arg])))
                print('    )')

                test_result = test_handle(**args)
                results[test['handle']] = test_result

            except Exception as err:
                print('Failed!')
                print('Error: %s' % str(err))
                break_flag = ''
                while not break_flag in ['y','n','Y','N'] and not test is test_config[-1]:
                    print('Continue? (y/n)')
                    break_flag = raw_input()
                if break_flag is 'n':
                    break
            else:
                print('Done.')
    return results

if '__main__' == __name__:
    result1 = run_threshold_test()

    # result1 = scan_threshold()
    # result2 = noise_test_internal_pulser()
