# v1.12 meter presentation, HA antenna control and BOOT gestures

Firmware **1.19-test3**, numeric software version **22**, removes the separate
antenna outlet introduced after v1.12. It keeps the original meter endpoint
and its On/Off cluster, which HA can expose as its native antenna switch.
The intended Apple Home presentation is only the native energy meter seen in
the user's v1.12 screenshots. Rebuilt Apple behavior remains unverified.

## Matter and HA model

- Root PartsList: `[1]`.
- Endpoint 1 type: Electrical Meter `0x0514` / 1300, revision 1.
- Endpoint 1 servers: Descriptor, EPM, EEM, original On/Off, vendor diagnostics
  and Keypad Input, with no added topology or Electrical Sensor type.
- Power path `1/144/8`; imported energy `1/145/1`; antenna state `1/6/0`.
- Antenna On means external; Off means internal. Commands persist `board_cfg`.
- No endpoint 2, dedicated Matter outlet or custom label provider.

The meter construction, power/energy, diagnostics, original On/Off creation and
keypad setup retain v1.12's code. Startup synchronization protects the saved
antenna choice against restored Matter attributes. The SML parser, report units,
per-board serial and Matter commissioning providers are unchanged.

HA can expose the original On/Off control even when Apple renders only the
Electrical Meter. This is controller presentation, not a different descriptor
or security permission per fabric. Keep the antenna entity excluded from any
HA HomeKit Bridge filters to avoid exporting a separate HAP control to Apple.

## BOOT behavior

| Gesture while firmware is running | Action |
| --- | --- |
| Hold 3–under 10 seconds, then release | Save the opposite antenna and reboot |
| Three short taps, each 50–700 ms with no gap over 2 seconds | Same antenna toggle and reboot |
| Hold 10 seconds | Matter factory reset |

The antenna hold waits for release so a longer factory-reset hold never toggles
the antenna first. Factory reset no longer triggers at five seconds. A failed
save does not reboot or alter the selected antenna. Antenna recovery gestures
preserve pairing, serial number and setup code. Timing uses unsigned elapsed
milliseconds and handles counter wrap.

## Validation

1. Install the single universal `IR_Power_Meter.ota` using Matter Server's local
   firmware upload. Keep power connected through reboot and the health check.
   This test build is excluded from the companion's stable-release discovery.
2. Confirm `1.19-test3` / 22. Use the configured HA MCP server for HA operations.
   Verify the model above and valid, changing native Power/Energy values.
3. Re-enable the original meter antenna entity if it was disabled. Confirm it
   agrees with the companion's Active antenna diagnostic. A stale endpoint-2
   entity is not the control used by this firmware.
4. Verify no HomeKit Bridge filter includes the antenna entity. Keep other
   exported devices and all existing HA histories intact.
5. Check Apple Energy for the original native meter appearance. Check existing
   discovery first; do not erase HA pairing or factory-reset to refresh Apple.
6. Test a 3-second hold/release and three taps in both antenna directions,
   with an external antenna connected and Thread coverage available. Confirm
   saved selection, reboot, pairing retention and recovery of live readings.
   Do not exercise the destructive 10-second factory reset on a production
   pairing merely to validate the button; its boundary is tested on the host.
7. Compare Apple totals with household demand while a separate metered plug
   runs. Native power visibility and avoidance of overlapping totals are
   separate checks; do not mark either passed without observing it.
