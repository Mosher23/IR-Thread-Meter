# IR Smart Meter — Matter over Thread

Use a Seeed XIAO ESP32-C6 and an optical SML head to read an electricity meter
over Matter/Thread. Home Assistant's built-in **Matter** integration shows
Energy and Power. The optional **IR Smart Meter** companion adds diagnostics,
optical PIN entry, and GitHub firmware updates.

> This is a development project, not a certified Matter product. It uses a
> test certificate, development vendor ID, and sample serial number.

## Choose your path

| If you... | Start here |
| --- | --- |
| Have a new XIAO | [Flash the latest firmware over USB](BOOTSTRAP_AND_OTA.md#first-time-usb-flash), then [add it to Matter](#add-the-meter-to-matter). |
| Have firmware 1.6 or older | [Do the one-time USB migration](BOOTSTRAP_AND_OTA.md#upgrading-from-firmware-older-than-17); do not erase the whole flash. |
| Have firmware 1.7 or newer | [Install the Home Assistant companion](#install-the-home-assistant-companion), then use **OTA Firmware** for later releases. |
| Already have a working Matter device | Add the companion only if you want PIN entry, diagnostics, or GitHub OTA. No re-pairing is needed. |

You need a XIAO ESP32-C6, a compatible **3.3 V UART** optical head, stable
power, and a Thread Border Router. Connect **head TX → XIAO GPIO17 (D7/RX)**
and a common ground. For optical PIN transmission, also connect
**XIAO GPIO16 (D6/TX) → head RX**. A head powered from the XIAO's 5 V pin
must still have a **3.3 V-safe UART output**. See [wiring details](firmware/README.md#hardware).

## Add the meter to Matter

1. Flash the firmware and power the XIAO within range of your Thread network.
2. Attach the IR head to the meter. If available, unlock detailed SML output
   (**InF ON**) first, so Power is present when Home Assistant discovers it.
3. In **Home Assistant → Settings → Devices & services**, add a **Matter**
   device using the setup code/QR from the firmware's USB serial monitor.
   Alternatively, add it to Apple Home first, then use **Turn On Pairing Mode**
   to share it with Home Assistant. Do not factory-reset an already-paired
   device just to add a second controller.
4. Look under the **Matter** device for native **Energy** and **Power** entities.
   Power is unknown until a valid SML power reading arrives.

If Power is **Unavailable** in HA but Apple Home or the Matter Server app
shows a live `ActivePower` value, reload the HA **Matter** integration while
the head is reading. HA Core 2026.9 can skip Power discovery when the value is
null at startup. Do not erase or re-pair the XIAO as a first step.

## Install the Home Assistant companion

The companion is optional and does **not** replace the Matter integration.
Install it after your meter appears in Home Assistant Matter.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mosher23&repository=IR-Thread-Meter&category=integration)

If the button does not add the repository:

1. Open **HACS → ⋮ → Custom repositories**. Add
   `https://github.com/Mosher23/IR-Thread-Meter` as an **Integration**.
2. Download **IR Smart Meter** from the `main` branch and restart Home
   Assistant. Firmware release tags are separate from integration updates.
3. Go to **Settings → Devices & services → Add integration → IR Smart Meter**
   and select your existing Matter device.

HACS installs only the HA companion, **not XIAO firmware**. For manual
installation, copy `custom_components/smartmeter` to
`/config/custom_components/smartmeter`, restart HA, and add the integration.

The companion provides **OBIS Received**, **Manufacturer**, and **Meter ID**
diagnostics; **Meter PIN** and **Send PIN** controls; and **OTA Firmware**.
It intentionally does **not** create another Power sensor.

### Enter a meter PIN

Type a four-digit PIN in **Meter PIN**, then press **Send PIN** within two
minutes. The digits remain only in memory; HA state/history get a masked
placeholder. The field clears after the send attempt. The IR transmit LED
must face the meter's optical **control** point, which may differ from the
SML reading point. See [optical PIN details](firmware/README.md#optical-pin-entry).

### Update firmware over Thread

After firmware **1.7 or newer** has been USB-bootstrapped, open the companion
device's **OTA Firmware** entity. Click **Install** when a compatible newer
release appears. The image is downloaded from GitHub, validated, transferred
via Matter Server, and followed by a XIAO reboot. **Updates never install
automatically.** Keep power and Thread connectivity stable. The separate
native Matter **Firmware** entity may show different update information; use
**OTA Firmware** for this repository's releases.
See the [USB and OTA guide](BOOTSTRAP_AND_OTA.md#update-over-thread).

## Troubleshooting

| Symptom | First check |
| --- | --- |
| Energy works; Power is unknown | Is the head aligned, and is detailed SML output enabled? Check **OBIS Received**. |
| Power is unavailable in HA but visible elsewhere | Reload **Matter** while the meter is transmitting. No re-pairing is needed. |
| Companion diagnostics are unknown | Confirm the Matter device is online and SML is received. Some meters omit ID/manufacturer OBIS fields. |
| Sending a PIN does not change the meter display | Check GPIO16 → head RX, transmit support, and optical control-point alignment. |
| OTA Firmware offers no update | Check `compatibility_issue` and `last_error` in Developer tools → States. The GitHub check runs every six hours; refresh the entity to check sooner. |

## Migrating an old `smartmeter_pin` installation

Companion version 2.0 renamed the domain and folder to `smartmeter`. HA
cannot migrate the old config entry automatically. Back up HA, remove **only**
the old companion entry, install this repository's `main` branch through
HACS, move the leftover `/config/custom_components/smartmeter_pin` folder
out of `custom_components`, restart HA, and add **IR Smart Meter** again
with the same Matter device. **Keep the Matter pairing.** Companion entity
IDs may change, so review dashboards and automations that reference them.

## More information

- [USB flashing, OTA, and release publishing](BOOTSTRAP_AND_OTA.md)
- [Firmware build, wiring, OBIS mapping, and commissioning](firmware/README.md)
- [Licensing and attribution](firmware/LICENSES.md)

The [latest firmware release](https://github.com/Mosher23/IR-Thread-Meter/releases/latest)
is currently v1.9 (Matter numeric version 10). Release checksums guard
against accidental corruption; this test-device setup does not provide
production signing, secure boot, or production Matter attestation.
