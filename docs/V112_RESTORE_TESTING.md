# v1.12 meter with a separate antenna control

**Result:** 1.19-test2 was installed and re-paired with live HA readings, but
Apple Home still showed only the outlet. The user requested the original
single meter endpoint with HA antenna control and a BOOT hold instead; see
[1.19-test3 testing](V112_HA_ANTENNA_TESTING.md).

The user's v1.12 screenshots show a native Electrical Meter with a lightning
icon, live wattage in Apple's Energy breakdown, and a Power row in its details.
This establishes that the earlier meter presentation worked. It supersedes any
inference from the failed split-endpoint tests that Apple cannot show this
meter as an energy accessory.

## Build

`1.19-test2`, numeric software version **21**, preserves the **v1.12 meter
model** and adds a separate synchronized antenna control. The original meter
retains its On/Off cluster; removing that cluster was a difference in the
unsuccessful 1.17–1.19-test1 models. Its exact influence on Apple's behavior
is still a hypothesis until this rebuild is tested.

The meter creation, diagnostic cluster, On/Off cluster and PIN-input setup
are retained from v1.12. The appended antenna endpoint, descriptive label and
synchronized callbacks use the v1.13 implementation. Startup synchronization
protects the saved RF selection. No new Electrical Sensor type or Power
Topology association is introduced.

One universal OTA is built, with `CONFIG_SMARTMETER_REQUIRE_BOARD_CONFIG=y`.
The saved antenna choice, serial number, Matter setup code and credentials
remain in their existing NVS partitions. No USB bootstrap, partition-table
rewrite or separate antenna binaries are part of this build. Version 21 lets
boards on `1.19-test1` (numeric 20) install it as a newer OTA image.

## Expected model

| Endpoint | Device type | Function |
| --- | --- | --- |
| 1 | Electrical Meter `0x0514` (1300), revision 1 | Original power, energy, antenna On/Off alias, PIN input and diagnostics |
| 2 | On/Off Plug-in Unit `0x010A` (266), revision 4 | Separate External Antenna control, without metering |

- Meter paths remain `1/144/8` for active power and `1/145/1` for imported energy.
- Antenna controls `1/6/0` and `2/6/0` are synchronized: On external, Off internal.
- The meter retains its original single device type and cluster set. No Power
  Topology server or added Electrical Sensor type is advertised.
- The new label provider only supplies endpoint 2's Fixed Label. It does not
  change the commissioning, serial-number or attestation providers.
- HA may expose both antenna aliases; both control the same physical RF switch.

## Physical check

1. Attach and power the IR reader, with detailed SML output enabled, and keep
   it attached through the test.
2. Upload `IR_Power_Meter.ota` using Matter Server's local firmware upload and
   install it on the existing meter. Keep power connected through reboot.
   The companion's stable-release checker does not offer this test version.
3. Confirm **1.19-test2 / 21** after reboot and after the rollback health check.
4. Use the configured HA MCP server for HA operations. Refresh discovery as
   needed and verify the model above, valid native Power/Energy values, and
   agreement between both antenna controls and the diagnostic. Check that each
   change is saved once, mirrors the other control and survives reboot.
5. Check Apple's **Energy → Power** breakdown for the native meter appearance
   shown in the v1.12 screenshots, and check the separate antenna control.
   Check existing pairing discovery first. Do not factory-reset the board or
   erase the HA pairing. Any Apple-only removal/re-add must be scoped explicitly
   because it can affect automations.
6. Compare Apple's total with physical household demand while another metered
   plug is running. Its load is already included in the household reading;
   Apple must not add it twice. The supplied screenshots establish individual
   power display, but do not independently establish this arithmetic.

Do not report the rebuilt image as hardware-verified until these checks pass.
