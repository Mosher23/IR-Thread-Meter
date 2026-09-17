# USB migration and future OTA updates

## Requirements

- XIAO ESP32-C6 with 4 MB flash and matching `0xFFF1`/`0x8000` test identity.
- Home Assistant Core 2026.9+, Matter Server app with API schema **13**+
  (Core 2026.9.2 and Matter Server app 9.2.0 were confirmed on this setup).
- Thread Border Router near the meter and stable power throughout updates.
- Python environment with `esptool`, and a USB data cable for the first step.
  You do **not** need local ESP-IDF if you use GitHub release assets.

## One-time v1.7 USB migration (external antenna)

Wait for a published release and download its standalone assets into **one
folder**: `bootloader.bin`, `partition-table.bin`, `ota_data_initial.bin`,
`IR_Power_Meter_external.bin`, `IR_Power_Meter_internal.bin`, `SHA256SUMS`,
and `flash.py`. No ZIP archive is needed. If you build locally, these files
are in `dist/release/`.

Disconnect the IR head only if needed to reach USB; check the actual serial
port name again. On your Mac:

```bash
cd "/path/to/downloaded-release-folder"
source "/Users/sergiitsiapenko/Documents/Codex/ESP32 Thread Meter/matter-thread-smartmeter-firmware/.venv/bin/activate"
python -m serial.tools.list_ports
python flash.py --port /dev/cu.usbmodem21201 --antenna external
```

Substitute `--antenna internal` for the built-in ceramic antenna. The script
verifies SHA-256 and asks you to type `FLASH` before writing. It writes the
bootloader, partition table, initial OTA selection and app; **it does not
erase the whole flash**, your paired Matter/Thread settings, or meter data.
The new board-config partition occupies previously unused flash at `0x3E6000`
and saves the chosen antenna on first boot. Flashing another variant later
does not override an existing saved antenna choice. Avoid `erase_flash`:
it destroys commissioning.

After boot, confirm the existing HA Matter device returns and reports firmware
`1.7`, and the companion update entity's `compatibility_issue` is empty.
If it does not reconnect, diagnose Thread and power before an OTA release.

## Install a subsequent release in Home Assistant

Install the custom integration by copying the directory
`custom_components/smartmeter_pin` from this repository to
`/config/custom_components/smartmeter_pin` and restart HA Core. If the
IR Smart Meter PIN integration was previously configured, its existing entry
stays and gains **Github OTA Firmware** on the companion device. Otherwise add it
in Settings → Devices & services and choose your Matter meter. HACS custom
repository installation can also use this layout.

The companion entity polls this repository's latest *stable* GitHub release
every six hours. It only offers an update when the release's numeric Matter
version is newer and compatible. It does **not** upload, flash, or reboot
until you click Install. On click it downloads the `.ota`, checks SHA-256 and
the Matter header/digest, uploads it to Matter Server, and commands the selected
node to update. It waits for the version after reboot and the firmware's
30-second health check before marking success. For failures inspect its
`ota_status`, `compatibility_issue`, and `last_error` attributes.
The native Matter **Firmware** entity may also appear: use the companion
**Github OTA Firmware** entity for on-demand GitHub fetching. Its available
version can differ from the installed version because it reflects whichever
Matter OTA provider HA knows about; it does not mean the meter downgraded.

GitHub and HA polls can take time to notice a new release; use **Update entity**
in HA Developer Tools to refresh earlier. A v1.7 USB-only release is
intentionally not offered for OTA installation.

## Building and publishing

Source ESP-IDF **v5.5.5** and ESP-Matter commit
`c91ddfbb08ccc74bb73dd6eca7422178f48b75e1` (release/v1.6), following
[`firmware/README.md`](firmware/README.md). This project carries one tiny
ESP-IDF NimBLE cast patch at
[`patches/esp-idf-nimble-conversion.patch`](patches/esp-idf-nimble-conversion.patch),
applied in CI; apply it to a fresh local SDK too.

```bash
bash scripts/build.sh internal
bash scripts/build.sh external
bash scripts/build.sh ota
python scripts/package_release.py --output dist/release
```

The two **USB bootstrap** builds choose an initial antenna. The universal
**OTA** build refuses to boot without a previously stored antenna selection.
`v1.7` packages only USB assets and a `delivery: usb` manifest—no `.ota` file.
The v1.8 source uses numeric Matter version `9` in
`firmware/main/MatterProjConfig.h`, `firmware/CMakeLists.txt`, and
`firmware/sdkconfig.defaults`, with string version `1.8` in the first two.
Increment all version markers together for later releases. The packaging
script refuses stale builds and oversize apps.

Push validated source, then create a stable GitHub release tagged exactly
`v1.7` or, for the next version, `v1.8`. GitHub Actions builds the pinned SDK,
tests the parser, checks the tag, and attaches individual assets with
`ota-manifest.json` **last**. Never publish two antenna `.ota` images with the
same VID/PID/version. Test a future image on an accessible meter before
announcing it: physical Thread OTA/rollback cannot be proven by local builds.

This public test release trusts the GitHub account/repo; it is not firmware
signing. For production replace test attestation, adopt signed firmware and
secure boot, and review device/controller authenticity end to end.
