'''
This module contains chip configuration files.
The format is a standard JSON file structured as follows:

.. parsed-literal::
    {
        "pixel_trim_thresholds": [<list of 32 5-bit integers>],
        "global_threshold": <8-bit integer>,
        "csa_gain": <1-bit integer>,
        "csa_bypass": <1-bit integer>,
        "internal_bypass": <1-bit integer>,
        "csa_bypass_select": [<list of 32 1-bit integers>],
        "csa_monitor_select": [<list of 32 1-bit integers>],
        "csa_testpulse_enable": [<list of 32 1-bit integers>],
        "csa_testpulse_dac_amplitude": <8-bit integer>,
        "test_mode": <1-bit integer>,
        "cross_trigger_mode": <1-bit integer>,
        "periodic_reset": <1-bit integer>,
        "fifo_diagnostic": <1-bit integer>,
        "sample_cycles": <8-bit integer>,
        "test_burst_length": <16-bit integer>,
        "adc_burst_length": <8-bit integer>,
        "channel_mask": [<list of 32 1-bit integers>],
        "external_trigger_mask": [<list of 32 1-bit integers>],
        "reset_cycles": <24-bit integer>
    }
All fields are necessary.
'''
pass
