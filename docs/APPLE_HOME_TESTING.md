# Apple Home independent-meter verification

Firmware **1.17**, Matter numeric software version **18**, restores an
independent Electrical Meter and removes the association between household
measurements and the antenna outlet. The previous outlet-style display worked
after fresh Apple discovery, but the user reported that it added household
power to loads already included in that measurement. The earlier independent
meter did not show that double counting. Verify the restored behavior on one
accessible meter before treating Apple Home behavior as confirmed.

## Intended Matter model

| Endpoint | Device type | Relevant servers |
| --- | --- | --- |
| 1 | Electrical Meter (`0x0514`) | Power (`0x0090`), energy (`0x0091`), PIN input, vendor diagnostics |
| 2 | On/Off Plug-in Unit (`0x010A`) | On/Off (`0x0006`), Fixed Label (`External antenna`) |

Endpoint 1 has one power and one energy source. It does not advertise the
Electrical Sensor utility type (`0x0510`) or Power Topology (`0x009C`). Endpoint
2 has no measurement clusters, and there is no whole-node or endpoint-set
power association with it. Measurement paths remain on endpoint 1; antenna
control remains on endpoint 2 to preserve HA's existing entity identities.

The antenna tile is intended to show only On/Off, with **On = external** and
**Off = internal**. The meter's energy presentation is independent. Apple
controls rendering; the firmware does not supply custom tile subtitles or
guarantee two separately displayed tiles.

## Install and inspect

1. Keep USB access and a known-good image available. Connect an external
   antenna before selecting it, and test where both antennas reach Thread.
2. Install the single universal `IR_Power_Meter.ota` through the companion's
   **OTA Firmware** entity for a published latest release, or Matter Server's
   local firmware-update interface for a candidate. The same image supports
   both saved antenna choices. The companion does not discover prereleases.
3. Confirm version `18` / `1.17` after reboot and again after one minute to
   check that rollback has not restored the previous image.
4. Through the configured HA MCP server, refresh the Matter interview and
   inspect descriptors. Expect `1/29/0` to contain Electrical Meter (`1300`),
   `2/29/0` to contain On/Off Plug-in Unit (`266`), and no cluster `156` in
   `1/29/1`. Endpoint 2 must not contain clusters `144` or `145`.
5. Confirm a non-null `1/144/8` ActivePower reading and updating imported and
   exported energy independently of Apple Home. Null startup measurements do
   not establish whether Apple's aggregation is correct.
6. Let Apple Home refresh. Check that the antenna control has no household
   watts attached. If discovery remains stale, an Apple-only remove/re-add may
   be needed; obtain approval before changing that pairing because Apple
   scenes and automations may need rebuilding. Keep the HA pairing intact.

Do not erase flash or factory-reset the XIAO to force a display refresh.
If an antenna loses Thread, use three short BOOT taps or the USB console's
`antenna internal` / `antenna external` recovery commands.

## Acceptance checks

- HA retains existing power/energy entity identities and histories; PIN,
  diagnostics and OTA still work.
- The antenna control shows On/Off without household watts. It changes only
  antenna selection, and the companion diagnostic agrees.
- Power and energy continue updating in both antenna states; Off does not
  produce a fabricated zero.
- Reboot retains the antenna choice and restores its reported state.
- Compare the physical meter with Apple's total while an independently metered
  plug is active. For example, if household demand is 500 W including a 100 W
  plug, Apple must not report 600 W by adding them together.
- Repeat with the plug switched off/on, allowing for reporting delays and other
  household load changes. Record whether Apple displays household demand or
  only its monitored-load sum; neither should add the same load twice.

Record Apple/home-hub OS versions, descriptors, screenshots, power readings
and results in both antenna states. Compilation and host tests do not prove
Apple rendering or energy aggregation. No Apple result for 1.17 is confirmed
until this physical test passes.
