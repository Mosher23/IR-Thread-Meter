# Matter-over-Thread Smart-meter Reader

This is an ESP32-C6 port of Claus Muus' `zigbee-smartmeter-reader`. It keeps the
byte-oriented SML parser and default OBIS mapping, but replaces the Arduino
Zigbee endpoint with a native ESP-IDF/ESP-Matter **Electrical Meter** endpoint
over the ESP32-C6's built-in Thread radio.

## Device identity

- Manufacturer: `SimpleIdeas`
- Product and commissionable name: `IR Power Meter`
- Development VID/PID: `0xFFF1` / `0x8000`
- Software version: `8` (`1.7`, USB-only bootstrap for later OTA)
- Hardware version: `1` (`1.0`)
- Development serial number: `00000001`
- ESP-IDF project name: `IR_Meter_Thread_Matter`

The serial number and test VID/PID are development values. Provision a unique
serial number and production Matter attestation credentials before producing
more than one device.

The default data model publishes:

| OBIS | Meter value | Matter cluster/value |
| --- | --- | --- |
| `1-0:16.7.0*255` | Active power | Electrical Power Measurement / ActivePower, mW |
| `1-0:1.8.0*255` | Imported energy | Electrical Energy Measurement / cumulative imported energy, mWh |
| `1-0:2.8.0*255` | Exported energy | Electrical Energy Measurement / cumulative exported energy, mWh |
| `1-0:96.1.0*255` | Physical meter ID | Read-only manufacturer-specific diagnostic string |
| `1-0:96.50.1*1` | Physical meter manufacturer | Read-only manufacturer-specific diagnostic string |

Unlike the original Zigbee version, no ioBroker or Zigbee2MQTT converter is
needed. A Matter controller reads the standard Matter energy clusters.
The two identity diagnostics remain empty if the meter does not transmit those
OBIS entries. Binary octet strings are displayed as uppercase hexadecimal;
printable values are displayed as text. The reader's own Matter vendor, product,
and serial information remain distinct from the physical meter's identity.

## Version baseline

This port is pinned to the latest published stable specifications and matching
Espressif release stack checked on 15 August 2026:

- Matter specification/data model: **Matter 1.6**
- ESP-Matter branch: `release/v1.6`
- ESP-Matter commit: `c91ddfbb08ccc74bb73dd6eca7422178f48b75e1`
- Espressif connectedhomeip commit: `93abd8e6891bb578ea63254fb29d099936f345c8`
- ESP-IDF: **v5.5.5**, the version recommended by that ESP-Matter release
- Thread: **Thread 1.4.0**, native OpenThread FTD on the ESP32-C6 radio

ESP-Matter `main` already targets the in-development Matter 1.7 data model, so
this project deliberately uses `release/v1.6` rather than a moving development
branch. Pinning commits keeps the generated Matter APIs reproducible.

OpenThread comes from ESP-IDF and is configured as Thread 1.4. Do not replace it
independently with an arbitrary upstream OpenThread checkout: Matter's platform
integration and radio configuration must remain version-compatible. Border
Router-only Thread facilities belong on the Thread Border Router, not this
meter endpoint.

## Hardware

Defaults target the Seeed XIAO ESP32-C6:

| Signal | XIAO pin | GPIO |
| --- | --- | --- |
| IR head TX -> ESP RX | D7/RX | 17 |
| ESP TX -> IR head RX (optional) | D6/TX | 16 |
| User LED | internal | 15 |
| Factory-reset button | BOOT | 9 |
| RF-switch control enable | internal | 3 |
| RF-switch antenna select | internal | 14 |

For a continuously transmitting SML meter, only `IR head TX -> GPIO17` and a
common ground are required. PIN transmission additionally requires
`GPIO16 -> IR head RX`. The UART is configured as 9600 baud, 8 data bits, no
parity, and 1 stop bit.

If reusing the Volkszaehler USB reader, connect GPIO17 to the meter-side TX
trace/CP2104 RXD trace. Do not connect the USB D+ or D- wires to the UART. Verify
that the tapped signal is 3.3 V before connecting it to the ESP32-C6.

## Build

Install ESP-IDF v5.5.5, then check out the pinned ESP-Matter release:

```bash
git clone --recursive --branch v5.5.5 https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32c6
source ./export.sh

cd ..
git clone --recursive --branch release/v1.6 https://github.com/espressif/esp-matter.git
cd esp-matter
git checkout c91ddfbb08ccc74bb73dd6eca7422178f48b75e1
git submodule update --init --recursive
./install.sh
source ./export.sh
```

Then build this project:

```bash
cd /path/to/matter-thread-smartmeter
idf.py set-target esp32c6
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash monitor
```

The project deliberately uses USB Serial/JTAG for logs so UART1 remains
dedicated to the IR reader.

The clean reference build completed successfully with a binary size of
approximately `0x19ed70` bytes and 14% free in the smallest application partition.

Two antenna variants can be built independently:

```bash
idf.py -B build-internal -D SDKCONFIG=sdkconfig.internal \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.internal.defaults' build

idf.py -B build-external -D SDKCONFIG=sdkconfig.external \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.external.defaults' build
```

On first boot these variants store the antenna choice in a separate `board_cfg`
NVS partition. Future universal OTA builds read that setting before enabling
the radio. Both variants drive GPIO3 low before configuring GPIO14. The
internal build drives GPIO14 low for ceramic; the external build drives it high
for U.FL/IPEX, following the
[official Seeed RF-switch sequence](https://wiki.seeedstudio.com/xiao_esp32c6_getting_started/#hardware-overview).

To change pins, baud rate, or report intervals:

```bash
idf.py menuconfig
```

Open **Smart-meter reader**. The defaults preserve the original five-second
minimum update interval and one-hour maximum refresh interval.

## Commissioning

You need a Matter controller and a Thread Border Router. After flashing, the
serial monitor prints the standard Matter setup payload/QR information. Add it
from your Matter ecosystem in the usual way.

For `chip-tool`, obtain the active Thread operational dataset from your Border
Router and commission with the setup code printed in the log:

```bash
chip-tool pairing ble-thread 1 hex:<ACTIVE_OPERATIONAL_DATASET> 20202021 3840
```

Example reads after commissioning (endpoint 1 is typical; use the endpoint
printed by the firmware):

```bash
# Electrical Power Measurement: ActivePower attribute 0x0008
chip-tool electricalpowermeasurement read active-power 1 1

# Electrical Energy Measurement: cumulative imported/exported energy
chip-tool electricalenergymeasurement read cumulative-energy-imported 1 1
chip-tool electricalenergymeasurement read cumulative-energy-exported 1 1
```

Controller UI support for the newer Matter Electrical Meter device type varies.
The device can commission and expose standards-compliant attributes even when a
particular controller has not yet created dashboard entities for those values.
Use `chip-tool` reads to distinguish controller UI limitations from firmware or
Thread failures.

## Operation

- The GPIO15 user LED slowly breathes while the firmware is running.
- Every CRC-valid SML frame produces a short full-brightness LED pulse, after
  which the breathing animation resumes.
- At startup, the serial log reports `Saved RF antenna: internal` or
  `Saved RF antenna: external`.
- Reports are emitted only after the complete SML frame passes its CRC check.
- Hold BOOT for five seconds while the firmware is running to erase Matter
  fabrics and Thread credentials.
- The Matter shell is enabled; `matter esp factoryreset` is an alternative.

## Optical PIN entry

The Electrical Meter endpoint also exposes a Matter **Keypad Input** server
with the Number Keys feature. A controller sends four numeric `SendKey`
commands followed by `Enter` (or `Select`). `Clear` or `Exit` cancels a partial
entry. The PIN is kept only in RAM, is never written to NVS, and is not printed
in firmware logs.

On `Enter`, the firmware pauses SML reception and drives the IR head through
UART TX on GPIO16. It sends two short activation flashes, emits the number of
short flashes represented by each digit, and leaves at least three seconds of
dark time between digits. A zero digit is represented by no flash during that
digit interval. SML reception resumes after the meter has checked the fourth
digit.

For first-time alignment and timing calibration, use the USB console while
watching the meter display:

```text
meter-pin 1234
```

The console echoes typed input, so use it only for local testing. Normal use
should send the Keypad Input commands over the encrypted Matter session. The
short-flash, inter-flash, wake-settle, digit-wait, and TX inversion settings are
available under **Smart-meter reader** in `idf.py menuconfig`.

On the EMH eHZB, the optical control element and the INFO/SML data interface
are physically distinct front-panel elements. The write LED must illuminate
the optical control element; depending on the head's optics, this can require
repositioning the head or using a dedicated IR LED. Confirm that the display
changes to PIN entry before trying a real PIN repeatedly, because the meter can
temporarily block further attempts after too many incorrect entries.

## Extending the OBIS map

Edit `kHandlers` in `main/smart_meter.cpp`. The Matter Electrical Power
Measurement cluster can also expose voltage, current, frequency, and power
factor, but each extra measurement requires:

1. adding its OBIS and SML unit;
2. enabling the corresponding optional Matter attribute;
3. implementing the delegate getter and change notification;
4. converting to Matter's required base unit, normally mV, mA, mW, or mHz.

## Attribution and licensing

The port is derived from:

- `zigbee-smartmeter-reader`, Copyright Claus Muus, GPL-3.0
- `sml_parser`, by olliiiver, LGPL-2.1
- ESP-Matter example patterns, Espressif Systems, CC0/public-domain example code

See [LICENSES.md](LICENSES.md). Preserve the upstream notices when
redistributing modified source.
