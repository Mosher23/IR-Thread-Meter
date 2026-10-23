# v1.20 release validation

Project: **SML over Matter/Thread**. Firmware display version: **1.20**.
Matter software version: **24**. One universal OTA uses the saved antenna choice.
The HA companion is version **2.1.4** and orders firmware updates numerically.

## Device model

- One Electrical Meter endpoint (`0x0514`) on endpoint 1.
- Power: `1/144/8`; imported energy: `1/145/1`; antenna state: `1/6/0`.
- No separate antenna outlet, topology server or additional sensor device type.
- Native HA Energy, Power and antenna control; optional companion diagnostics,
  optical PIN/display commands and GitHub OTA updates.
- Apple Home uses the native meter presentation confirmed by the user in test3.
  This release keeps that meter construction and adds LED feedback and naming.
- Exclude the HA antenna entity from HomeKit Bridge exports. Presentation is
  controller-specific; this is not per-fabric protocol access filtering.

## Button and LED

- Hold BOOT for 3 seconds, then release before 10 seconds: save the opposite
  antenna, flash the status LED three times, and reboot.
- Three short taps: the same saved toggle, confirmation and reboot.
- Hold for 10 seconds: Matter factory reset.
- Confirmation: three 80 ms on / 80 ms off flashes, overriding breathing and
  receive pulses. A save failure produces no success flashes or reboot.
- LED failure does not block antenna recovery indefinitely.
- Antenna gestures preserve pairings, per-board serial and Matter setup code.

## Automated checks

The host suite exercises actual C++ button/antenna/LED routines, including
hold thresholds, debounce, counter wrap, saved choice failures, LED exclusivity,
completion before restart, and bounded failure recovery. OTA tests validate
manifest identity, numeric ordering, image structure, embedded version, size
and SHA-256. The SML identity parser has a separate C++ test.

The release build uses the pinned SDKs in the firmware guide, with rollback
and saved board configuration enabled. Release assets include exact build
metadata and checksums. The OTA image is validated before upload and uploaded
asset digests are checked before publication.

## Hardware status

The user confirmed that the single-meter model works in Apple Home. The new
LED pattern and this final v1.20 binary still require a physical check. Validate
with the reader powered and attached to a transmitting meter: confirm live
readings, antenna changes in both directions, three LED flashes, restart,
pairing retention and recovery of readings. Do not factory-reset a production
pairing merely to test the reset boundary. Household aggregation must be
observed separately before claiming deduplication was verified.
