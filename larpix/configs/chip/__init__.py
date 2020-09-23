'''
This module contains chip configuration files. They are formatted as standard
JSON files with the following fields: ``"_config_type"``, ``"class"``, and
``"register_values"``. The ``_config_type`` field should always be set to
``"chip"`` and is used for validation when loading the configuration. An
optional ``"_include"`` field can be used to specify other configurations to
inherit configuration values from. Configuration inheritance occurs in the order
specified in the list so if a conflict is encountered, fields from a file later
in the list will overwrite fields from a file earlier in the list.

Additionally, the ``class`` field provides additional validation. There are two
configuration classes: ``"Configuration_v1"``, ``"Configuration_v2"``, and ``"Configuration_Lightpix_v1"``, each
corresponding to its respective ``larpix.configuration`` class. Attempting to
load a ``Configuration_v1`` config file to a ``Configuration_v2`` object and
vice versa will raise a runtime error.

The ``register_values`` field is a dict of the register name and the value to
use. All non-default fields should be specified, but it is recommended to use no
more than the minimum required. The following is an example of a partially-specified v2 configuration
file, which will maintain the current configuration except for the specified fields::

      {
            "_config_type": "chip",
            "_include": []
            "class": "Configuration_v2",
            "register_values": {
                  "enable_periodic_reset": 1,
                  "enable_periodic_trigger": 1,
                  "enable_rolling_periodic_trigger": 1,
                  "periodic_trigger_cycles": 100000
            }
      }

Here is an example using the configuration file inheritance::

      {
            "_config_type": "chip",
            "_include": ["chip/default_v2.json"]
      }

Which will be expanded to be the equivalent of::

      {
            "_config_type": "chip",
            "_include": [],
            "class": "Configuration_v2",
            "register_values": {
                  "pixel_trim_dac": [16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16],
                  "threshold_global": 255,
                  "csa_gain": 1,
                  "csa_bypass_enable": 0,
                  "bypass_caps_en": 1,
                  "csa_enable": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                  "ibias_tdac": 8,
                  "ibias_comp": 8,
                  "ibias_buffer": 8,
                  "ibias_csa": 8,
                  "ibias_vref_buffer": 8,
                  "ibias_vcm_buffer": 8,
                  "ibias_tpulse": 6,
                  "ref_current_trim": 16,
                  "override_ref": 0,
                  "ref_kickstart": 0,
                  "vref_dac": 219,
                  "vcm_dac": 77,
                  "csa_bypass_select": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                  "csa_monitor_select": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                  "csa_testpulse_enable": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                  "csa_testpulse_dac": 0,
                  "current_monitor_bank0": [0, 0, 0, 0],
                  "current_monitor_bank1": [0, 0, 0, 0],
                  "current_monitor_bank2": [0, 0, 0, 0],
                  "current_monitor_bank3": [0, 0, 0, 0],
                  "voltage_monitor_bank0": [0, 0, 0],
                  "voltage_monitor_bank1": [0, 0, 0],
                  "voltage_monitor_bank2": [0, 0, 0],
                  "voltage_monitor_bank3": [0, 0, 0],
                  "voltage_monitor_refgen": [0, 0, 0, 0, 0, 0, 0, 0],
                  "digital_monitor_enable": 1,
                  "digital_monitor_select": 0,
                  "digital_monitor_chan": 0,
                  "slope_control0": 0,
                  "slope_control1": 0,
                  "slope_control2": 0,
                  "slope_control3": 0,
                  "chip_id": 1,
                  "load_config_defaults": 0,
                  "enable_fifo_diagnostics": 0,
                  "clk_ctrl": 0,
                  "enable_miso_upstream": [0, 0, 0, 0],
                  "enable_miso_downstream": [0, 0, 0, 0],
                  "enable_miso_differential": [0, 0, 0, 0],
                  "enable_mosi": [0, 0, 0, 0],
                  "test_mode_uart0": 0,
                  "test_mode_uart1": 0,
                  "test_mode_uart2": 0,
                  "test_mode_uart3": 0,
                  "enable_cross_trigger": 0,
                  "enable_periodic_reset": 0,
                  "enable_rolling_periodic_reset": 0,
                  "enable_periodic_trigger": 0,
                  "enable_rolling_periodic_trigger": 0,
                  "enable_periodic_trigger_veto": 1,
                  "enable_hit_veto": 1,
                  "adc_hold_delay": 0,
                  "adc_burst_length": 0,
                  "channel_mask": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                  "external_trigger_mask": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                  "cross_trigger_mask": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                  "periodic_trigger_mask": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                  "periodic_reset_cycles": 4096,
                  "periodic_trigger_cycles": 0,
                  "enable_dynamic_reset": 0,
                  "enable_min_delta_adc": 0,
                  "threshold_parity": 1,
                  "reset_length": 1,
                  "mark_first_packet": 1,
                  "reset_threshold": 0,
                  "min_delta_adc": 0,
                  "digital_threshold": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            }
      }

'''
pass
