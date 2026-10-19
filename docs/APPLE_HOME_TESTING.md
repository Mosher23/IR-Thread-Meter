# Apple Home metering-outlet verification

Firmware **1.16**, Matter numeric software version **17**, changes the device
classification and power topology after the 1.15 test still showed a generic
meter tile without On/Off state or watts. The 1.16 tile behavior needs hardware
verification. Test on one accessible meter first.

## Intended behavior

| Selected antenna | Outlet state | Example tile |
| --- | --- | --- |
| External U.FL/IPEX | On | Smart Meter — On · 220 W |
| Internal ceramic | Off | Smart Meter — Off · 220 W |

The watts are the SML meter reading, not the antenna or ESP32's consumption.
Tapping the outlet selects an antenna. Off does not shut down the reader or
zero its measurements. Apple controls the subtitle and may choose different
formatting or omit watts. The firmware cannot supply a custom subtitle such
as "External" or "Internal".

## Matter model

| Endpoint | Device types | Relevant servers |
| --- | --- | --- |
| 1 | Electrical Sensor (`0x0510`, utility) | Power (`0x0090`), energy (`0x0091`), Power Topology (`0x009C`), PIN input, vendor diagnostics |
| 2 | On/Off Plug-in Unit (`0x010A`) | On/Off (`0x0006`), Fixed Label (`Smart Meter`) |

Endpoint 1's Power Topology FeatureMap is `1` (NodeTopology), describing
whole-device measurements. AvailableEndpoints and ActiveEndpoints are absent.
There is one measurement source and one antenna switch. The outlet is now the
sole application device type; the additional Electrical Meter (`0x0514`) type
is no longer advertised. Existing Home Assistant measurement paths stay on
endpoint 1, and antenna control stays on endpoint 2.

This uses the same application and utility device types and NodeTopology
feature reported for the [IKEA GRILLPLATS plug](https://matter-survey.org/device/grillplats-plug-4476-4096).
Endpoint numbers remain unchanged to preserve existing HA entities.
The [Matter device library](https://csa-iot.org/wp-content/uploads/2024/05/matter-1-3-device-library-specification.pdf)
defines Electrical Sensor as a utility device whose measurements follow its
Power Topology cluster. Matching this model does not prove Apple Home rendering.

## Install and inspect

1. Keep USB access to the XIAO and record its current firmware version. Keep a
   known-good firmware image available. Connect an external antenna before
   selecting it, and test where both antennas can reach Thread.
2. Install `IR_Power_Meter.ota` using the companion's **OTA Firmware** entity
   for a published latest release, or Matter Server's local firmware-update
   interface for a candidate. The companion does not discover prereleases.
3. Confirm software version `17` / `1.16` after reboot and again after one
   minute, to check that rollback has not restored the previous image.
4. In Matter Server, run **Interview**, then reload Home Assistant's **Matter**
   integration. Inspect the device's endpoint/attribute data for the model
   above. Verify `1/29/0` (DeviceTypeList) contains only Electrical Sensor,
   `2/29/0` contains the outlet, and `1/156/65532` (FeatureMap) is `1`.
   AvailableEndpoints and ActiveEndpoints must not be advertised by the topology
   server. Confirm a non-null live `1/144/8` (ActivePower) reading independently
   of the Apple Home tile.
5. Allow Apple Home to refresh the accessory. Restart its active home hub if
   necessary and inspect the controllable outlet, naming it **Smart Meter**
   if its display name differs. Keep Matter pairings intact for this test.

Do not erase flash or factory-reset the XIAO to force a display refresh.
If switching antennas loses Thread, tap BOOT three times to toggle back,
or use `antenna internal` / `antenna external` on the USB console.

## Acceptance checks

- The controllable Apple Home tile shows both On/Off and live watts.
- On selects external; Off selects internal. The companion's **Active antenna**
  diagnostic agrees with the selection.
- SML power keeps updating in both states. Internal antenna does not create a
  zero-power reading simply because the outlet is Off.
- The Energy tab has no extra meter contributing the same measurements twice.
- Home Assistant's existing power/energy entities and histories remain attached;
  PIN entry, diagnostics, and OTA remain usable.
- Reboot retains the antenna and restores the reported On/Off state.

Record Apple Home and home-hub OS versions, before/after screenshots, Matter
endpoint data, and the results in both antenna states. A successful build and
host tests do not establish these UI results. If the old generic tile remains,
first determine whether Apple is still using the old Descriptor data. Do not
remove its Matter fabric or reset the reader just to experiment with discovery.
