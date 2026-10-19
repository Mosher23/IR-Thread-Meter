# Apple Home metering-outlet candidate

Firmware **1.15**, Matter numeric software version **16**, is a development
candidate. Its Apple Home tile behavior has not been verified on hardware.
It is not a stable release and should be tested on one accessible meter first.

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
| 1 | Electrical Meter (`0x0514`), Electrical Sensor (`0x0510`) | Power (`0x0090`), energy (`0x0091`), Power Topology (`0x009C`), PIN input, vendor diagnostics |
| 2 | On/Off Plug-in Unit (`0x010A`) | On/Off (`0x0006`), Fixed Label (`Smart Meter`) |

Endpoint 1's Power Topology FeatureMap is `4` (SetTopology).
AvailableEndpoints is `[2]`. There is no DynamicPowerFlow feature, so
ActiveEndpoints is not advertised. There is one measurement source and one
antenna switch. Existing Home Assistant measurement paths stay on endpoint 1.

## Install and inspect

1. Keep USB access to the XIAO and record its current firmware version. Keep a
   known-good firmware image available. Connect an external antenna before
   selecting it, and test where both antennas can reach Thread.
2. Upload the candidate `IR_Power_Meter.ota` through Matter Server's local
   firmware-update interface. The companion follows stable GitHub releases;
   an unpublished candidate will not appear in its **OTA Firmware** entity.
3. Confirm software version `16` / `1.15` after reboot and again after one
   minute, to check that rollback has not restored the previous image.
4. In Matter Server, run **Interview**, then reload Home Assistant's **Matter**
   integration. Inspect the device's endpoint/attribute data for the model
   above. In particular, read `1/156/0` (AvailableEndpoints) and
   `1/156/65532` (FeatureMap).
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
host tests do not establish these UI results. If watts still appear only in
Energy, retain this evidence before trying a different endpoint layout.
