# ⚡ IR Smart Meter — Matter over Thread

Use a Seeed XIAO ESP32-C6 and an optical SML head to read an electricity meter
over Matter/Thread. Home Assistant's built-in **Matter** integration shows
Energy and Power. The optional **IR Smart Meter** companion adds diagnostics,
optical PIN entry, and GitHub firmware updates.

✅ **Tested with an EMH eHZB electricity meter.** Other meters need compatible
SML output and OBIS values; optical PIN and display controls depend on the
meter model. See the [supported readings](firmware/README.md#device-identity).

> This is a development project, not a certified Matter product. It uses a
> test certificate, development vendor ID, and sample serial number.

## 🧰 What you need

- A Seeed **XIAO ESP32-C6 with 4 MB flash**, a USB data cable, and stable power.
- An electricity meter with **SML output** and a compatible **3.3 V UART** optical head.
- A **Thread Border Router** and a Matter controller, such as Home Assistant.
- For companion OTA updates: **Home Assistant Core 2026.9+** and a Matter
  Server app with **API schema 13+**.

Connect **head TX → XIAO GPIO17 (D7/RX)** and a common ground. For optical
PIN transmission, also connect **XIAO GPIO16 (D6/TX) → head RX**. A head
powered from the XIAO's 5 V pin must still have a **3.3 V-safe UART output**.
See [wiring details](firmware/README.md#hardware).

## 🚀 Setup

### Flash the firmware

Follow the [first-time USB flashing guide](BOOTSTRAP_AND_OTA.md#first-time-usb-flash)
and choose a [release with USB bootstrap files](https://github.com/Mosher23/IR-Thread-Meter/releases).
OTA-only releases are for boards that have already been set up.
Choose the internal antenna image, or the external image if an external
antenna is attached.

### Add the meter to Matter

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

### Install the Home Assistant companion

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

| Integration | Entities and controls |
| --- | --- |
| Home Assistant Matter | Native **Energy**, **Power**, and an independent **External antenna** on/off control. |
| IR Smart Meter companion | **OBIS Received**, **Manufacturer**, **Meter ID**, and **Active antenna** diagnostics; **Meter PIN**, **Send PIN**, **Short light pulse**, **Long light pulse**, and **OTA Firmware**. |

The companion uses your existing Matter device and does not create another
Power sensor. No re-pairing is needed to add it. Keep the companion updated
through HACS; its version is independent of the XIAO firmware version.

## 🎛️ Using the meter

### Select the antenna

The firmware exposes one **External antenna** control
(Matter endpoint 2). **Off means the built-in ceramic antenna; On means the
external U.FL/IPEX antenna.** Power, Energy, PIN commands, and diagnostics
remain on the meter endpoint.

The antenna control uses Matter's plug-in unit device type, so a controller
may display it as an outlet or give it a generic name. Rename that control
**External antenna** in Home Assistant or Apple Home if needed. The firmware
supplies this label, but each controller chooses its display name. The
companion's **Active antenna** diagnostic displays the actual selection.

Firmware **1.18** exposes an independent **Electrical Meter** with its required
**Electrical Sensor** component on endpoint 1, and the **External antenna**
control on endpoint 2. TreeTopology scopes household power and energy to the
meter endpoint without associating them with the antenna outlet. Switching
antennas does not stop measurement or zero the readings. The antenna tile is intended to show only
On/Off; power belongs to the meter's energy presentation, not that tile.

If the control is missing in Home Assistant, run **Interview** in Matter
Server and reload the **Matter** integration. Apple Home can cache the device
model, so verify that it has discovered the independent meter and antenna
control. The restored model's energy totals still need physical verification;
see the [test guide](docs/APPLE_HOME_TESTING.md) and
[antenna details](firmware/README.md#antenna-selection).

The selection takes effect immediately and is saved across reboots, OTA, and
Matter factory resets. Connect the external antenna *before* switching to it.
If the newly selected antenna cannot reach the Thread network, HA cannot send
the reverse command. Tap the XIAO's **BOOT button three times** while it is
running to toggle to the other antenna and restart. You can also use the USB
console command `antenna internal` or `antenna external` to select an antenna
and restart. These recovery actions preserve Matter credentials.

### Enter a meter PIN

Type a four-digit PIN in **Meter PIN**, then press **Send PIN** within two
minutes. The digits remain only in memory; HA state/history get a masked
placeholder. The field clears after the send attempt. The IR transmit LED
must face the meter's optical **control** point, which may differ from the
SML reading point. See [optical PIN details](firmware/README.md#optical-pin-entry).

### Navigate the meter display manually

Press **Short light pulse** for one 500 ms flash or **Long light pulse** for
one 5-second flash. These use the same GPIO16 optical TX head as Send PIN and
pause SML reception while transmitting. Watch the physical meter display;
the button confirms that the pulse was accepted for transmission, not that
the meter acted on it. EMH defines a long press as over 4.5 seconds.

**Be careful with Long light pulse:** its action depends on the currently
displayed meter menu item. On some screens it can toggle InF or erase
historical readings. Do not press it on an E CLr or HIS CLr confirmation
screen unless you intend to clear those values.

## 🔄 Firmware updates

Open the companion device's **OTA Firmware** entity in Home Assistant.
Click **Install** when a compatible newer release appears. The image is
downloaded from GitHub, validated, transferred via Matter Server, and followed
by a XIAO reboot. **Updates never install
automatically.** Keep power and Thread connectivity stable. The separate
native Matter **Firmware** entity may show different update information; use
**OTA Firmware** for this repository's releases.
See the [USB and OTA guide](BOOTSTRAP_AND_OTA.md#update-over-thread).

## 🛠️ Troubleshooting

| Symptom | First check |
| --- | --- |
| Energy works; Power is unknown | Is the head aligned, and is detailed SML output enabled? Check **OBIS Received**. |
| Power is unavailable in HA but visible elsewhere | Reload **Matter** while the meter is transmitting. No re-pairing is needed. |
| Companion diagnostics are unknown | Confirm the Matter device is online and SML is received. Some meters omit ID/manufacturer OBIS fields. |
| Sending a PIN does not change the meter display | Check GPIO16 → head RX, transmit support, and optical control-point alignment. |
| OTA Firmware offers no update | Check `compatibility_issue` and `last_error` in Developer tools → States. The GitHub check runs every six hours; refresh the entity to check sooner. |
| Device disconnects after changing the antenna | Check that the selected antenna is attached. Tap BOOT three times while running to toggle to the other antenna, or select one with `antenna internal` / `antenna external` in the USB console. |
| External antenna control is missing in HA | Run **Interview** in Matter Server, then reload **Matter**. The control is a separate endpoint and may appear as an outlet. |

## 📚 More information

- [USB flashing, OTA, and release publishing](BOOTSTRAP_AND_OTA.md)
- [Firmware build, wiring, OBIS mapping, and commissioning](firmware/README.md)
- [Licensing and attribution](firmware/LICENSES.md)

Release checksums guard against accidental corruption; this test-device setup
does not provide production signing, secure boot, or production Matter attestation.

## 💛 Sponsor this project

If this project helps you, you can support its development. Thank you! ☕

- [Ko-fi](https://ko-fi.com/mosher23)
- [Buy Me a Coffee](https://buymeacoffee.com/sergiit)
- [PayPal](https://paypal.me/mosher88)
