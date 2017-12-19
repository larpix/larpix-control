'''
Run basic noise tests for chips
  Note: Reset chips before each test.
'''

from __future__ import absolute_import
from larpix.quickstart import quickcontroller
from larpix.larpix import flush_logger
import time


def scan_threshold(controller=None, board='pcb-5', chip_idx=0,
                   channel_list=range(32), threshold_min_coarse=26,
                   threshold_max_coarse=37, threshold_step_coarse=1,
                   saturation_level=1000):
    '''Scan the signal rate versus channel threshold'''
    # Create controller and initialize chips to appropriate state
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
        print('  created controller')
    # Get chip under test
    chip = controller.chips[chip_idx]
    results = {}
    global_threshold_orig = chip.config.global_threshold
    channel_mask_orig = chip.config.channel_mask[:]
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
                           threshold_max_coarse,
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
            controller.run(0.1,'scan threshold')
            print('    done reading')
            # Process data
            packets = controller.reads[-1]
            adc_mean = 0
            adc_rms = 0
            if len(packets)>0:
                print('    processing packets: %d' % len(packets))
                adcs = [p.dataword for p in packets]
                adc_mean = sum(adcs)/float(len(adcs))
                adc_rms = (sum([abs(adc-adc_mean) for adc in adcs])
                           / float(len(adcs)))
            n_packets.append(len(packets))
            adc_means.append(adc_mean)
            adc_rmss.append(adc_rms)
            print(    '%d %d %0.2f %0.4f' % (threshold, len(packets),
                                             adc_mean, adc_rms))
            if len(packets)>saturation_level:
                # Stop scanning if saturation level is hit.
                break
        results[channel] = [thresholds[:], n_packets[:],
                            adc_means[:], adc_rmss[:]]
    # Restore original global threshold and channel mask
    chip.config.global_threshold = global_threshold_orig
    controller.write_configuration(chip,32)
    chip.config.channel_mask = channel_mask_orig
    controller.write_configuration(chip,[52,53,54,55])
    if close_controller:
        controller.serial_close()
    return results

def test_leakage_current(controller=None, chip_idx=0, board='pcb-5', reset_cycles=4096,
                         global_threshold=125, trim=16, run_time=1, channel_list=range(32)):
    '''Sets chips to high threshold and counts number of triggers'''
    close_controller = False
    if controller is None:
        close_controller = True
        controller = quickcontroller(board)
    
    chip = controller.chips[0]
    print('initial configuration for chip %d' % chip.chip_id)
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
    print('  clear buffer')
    controller.run(2,'clear buffer')
    del controller.reads[-1]
    for channel in channel_list:
        chip.config.disable_channels()
        chip.config.enable_channels([channel])
        controller.write_configuration(chip,range(52,56))
        # flush buffer
        print('  clear buffer')
        controller.run(0.1,'clear buffer')
        del controller.reads[-1]
        # run for run_time
        print('  begin test (runtime = %.1f)' % run_time)
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
    # Get chip under test
    chip = controller.chips[chip_idx]
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
    #chip.config.enable_analog_monitor(pulse_channel)
    #controller.write_configuration(chip,range(38,42)) # monitor
    controller.write_configuration(chip,range(32)) # trim
    controller.write_configuration(chip,[32,47]) # global threshold / xtrig
    print('Finished initial configuration')
    # Pulse chip n times
    dac_level = testpulse_dac_max
    lost = 0
    extra = 0
    controller.run(0.1, 'clear buffer')
    del controller.reads[-1]
    time.sleep(csa_recovery_time)
    for pulse_idx in range(n_pulses):
        if dac_level < (testpulse_dac_min + pulse_dac):
            # Reset DAC level if it is too low to issue pulse
            chip.config.csa_testpulse_dac_amplitude = testpulse_dac_max
            controller.write_configuration(chip,46)
            time.sleep(reset_dac_time) # Wait for front-end to settle
            print('  Reset DAC value')
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
        print('Pulse: %4d, Received: %4d, DAC: %4d' % (pulse_idx, len(result), dac_level))

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
    #chip.config.disable_analog_monitor(pulse_channel)
    #controller.write_configuration(chip,range(38,42)) # monitor
    # Keep a handle to chip data, and return
    result = controller.reads
    flush_logger()
    if close_controller:
        controller.serial_close()
    print('Pulses with # trigs > 1: %4d, Missed trigs: %4d' % (extra, lost))
    return result


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

def examine_global_scan(coarse_data, saturation_level=10000):
    '''Examine coarse threshold scan results, and determine optimum threshold'''
    result = {}
    sat_threshes = []
    chan_level_too_high = []
    chan_level_too_low = []
    for (channel_num, data) in coarse_data.iteritems():
        thresholds = data[0]
        npackets = data[1]
        saturation_thresh = -1
        saturation_npacket = -1
        # Only process if not already saturated
        if npackets[0] > saturation_level:
            chan_level_too_high.append(channel_num)
            continue
        if npackets[-1] <= saturation_level:
            chan_level_too_low.append(channel_num)
            continue
        for (thresh, npacket) in zip(thresholds, npackets):
            if npacket > saturation_level:
                saturation_thresh = thresh
                saturation_npacket = npacket
                sat_threshes.append(saturation_thresh)
                break
        result[channel_num] = {'saturation_thresh_global':saturation_thresh,
                               'saturation_npacket':saturation_npacket}
    # Collect other relevant results
    result['chan_level_too_high'] = chan_level_too_high
    result['chan_level_too_low'] = chan_level_too_low
    result['mean_thresh'] = sum(sat_threshes)/float(len(sat_threshes))
    return result


def run_threshold_test():
    # Run test
    cont = quickcontroller()
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




if '__main__' == __name__:
    result1 = run_threshold_test()

    # result1 = scan_threshold()
    # result2 = noise_test_internal_pulser()
