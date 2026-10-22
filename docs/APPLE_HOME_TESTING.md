# Apple Home independent-meter verification

Firmware **1.18**, Matter numeric software version **19**, adds the required
Electrical Sensor component to the independent Electrical Meter and scopes its
measurements to that endpoint with TreeTopology. In a fresh Apple Home pairing,
1.17 showed only the antenna control and omitted the meter from Energy even
while HA received live readings. Adding the missing component is a firmware
model correction; Apple rendering and aggregation still need physical testing.

## Intended Matter model

| Endpoint | Device type | Relevant servers |
| --- | --- | --- |
| 1 | Electrical Meter (`0x0514`) + Electrical Sensor (`0x0510`) | Power (`0x0090`), energy (`0x0091`), Power Topology (`0x009C`), PIN input, vendor diagnostics |
| 2 | On/Off Plug-in Unit (`0x010A`) | On/Off (`0x0006`), Fixed Label (`External antenna`) |

Endpoint 1 has one power and one energy source. Matter 1.6 Device Library
§14.8.3 requires the Electrical Sensor component. Its mandatory Power Topology
uses TreeTopology (FeatureMap `2`), which covers the meter and its children.
Endpoint 1's PartsList (`1/29/3`) is empty; endpoint 2 is a sibling, not a child.
The antenna therefore has no power/energy association. NodeTopology,
SetTopology, AvailableEndpoints and ActiveEndpoints are not advertised.
Measurement paths remain on endpoint 1 and antenna control on endpoint 2.

Specification references: [Device Library §14.8.3](https://csa-iot.org/wp-content/uploads/2026/06/23-27351-010_Matter-1.6-Device-Library-Specification.pdf),
[Power Topology model](https://github.com/project-chip/connectedhomeip/blob/93abd8e6891bb578ea63254fb29d099936f345c8/data_model/1.6/clusters/PowerTopology.xml).

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
3. Confirm version `19` / `1.18` after reboot and again after one minute to
   check that rollback has not restored the previous image.
4. Through the configured HA MCP server, refresh the Matter interview and
   inspect descriptors. Expect `1/29/0` to contain Electrical Meter (`1300`)
   and Electrical Sensor (`1296`), `1/156/65532` to equal `2`, `1/29/3` to be
   empty, and `2/29/0` to contain On/Off Plug-in Unit (`266`). Endpoint 2 must
   not contain clusters `144`, `145` or `156`. There must still be only one
   power and one energy measurement server.
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
- The independent meter appears in Apple's Energy presentation with live
  readings. An antenna-only tile without any meter entry fails this check.
- Compare the physical meter with Apple's total while an independently metered
  plug is active. For example, if household demand is 500 W including a 100 W
  plug, Apple must not report 600 W by adding them together.
- Repeat with the plug switched off/on, allowing for reporting delays and other
  household load changes. Record whether Apple displays household demand or
  only its monitored-load sum; neither should add the same load twice.

Record Apple/home-hub OS versions, descriptors, screenshots, power readings
and results in both antenna states. Compilation and host tests do not prove
Apple rendering or energy aggregation. No Apple result for 1.18 is confirmed
until this physical test passes.
