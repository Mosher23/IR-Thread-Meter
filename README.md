# IR Power Meter — Matter over Thread for XIAO ESP32-C6

IR SML reader with Matter energy and power measurements, PIN input,
physical-meter diagnostics, and a Home Assistant companion update entity.
Firmware source is in [`firmware/`](firmware/); the HA custom integration is
in [`custom_components/smartmeter/`](custom_components/smartmeter/).

## Install the Home Assistant integration with HACS

[![Open this integration in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mosher23&repository=IR-Thread-Meter&category=integration)

The button opens this custom repository in your Home Assistant HACS. If it has
not been added yet, use the manual steps below:

1. In HACS, open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/Mosher23/IR-Thread-Meter` with category **Integration**.
3. Open **IR Smart Meter** in HACS and download it. Select the `main` branch
   when asked for a version: the firmware release tags are separate from the
   latest integration code.
4. Restart Home Assistant, then go to **Settings → Devices & services → Add
   integration → IR Smart Meter** and select your already-commissioned Matter
   meter. Do not remove the Matter device or erase its pairing.

HACS installs only the Home Assistant integration, not ESP32 firmware. The
firmware's **OTA Firmware** entity handles subsequent device updates. For
manual installation, see the [bootstrap guide](BOOTSTRAP_AND_OTA.md#install-a-subsequent-release-in-home-assistant).

### Existing `smartmeter_pin` installations

Version 2.0 renames the Home Assistant domain as well as the folder. Home
Assistant cannot automatically transfer an existing `smartmeter_pin` config
entry to `smartmeter`. Back up Home Assistant first. Remove only the old
**IR Smart Meter** companion entry under **Settings → Devices & services**;
leave the **Matter** device and its pairing in place. Download this repository's
`main` branch in HACS. If `/config/custom_components/smartmeter_pin` remains,
move that old folder out of `custom_components` as a backup, then restart Home
Assistant and add **IR Smart Meter** again, choosing the same Matter device.
Companion entity IDs may change, so check any dashboards or automations that
reference them. The meter firmware and native Matter Energy/Power entities do
not change.

The first release (`v1.7`) is a **USB-only migration**. It adds a persistent
antenna setting, updated partition table, and bootloader rollback. It cannot
safely be installed over Thread from older v1.6 firmware. Flash it once for
your internal/external antenna using the [migration guide](BOOTSTRAP_AND_OTA.md).
Later versions, including v1.9 (numeric Matter version 10),
can be installed via the companion **OTA Firmware** entity in Home
Assistant once their release assets are published. Nothing installs
automatically; the user must click Install.

The companion integration reads meter diagnostics and firmware version every 30
seconds. Power is exposed only by Home Assistant's native Matter integration;
it remains unknown until the meter sends a valid SML power reading. When adding
the Matter device to Home Assistant for the first time, keep the IR head on the
meter so Power is non-null during discovery. To enter a PIN, set the **Meter PIN** field,
then press **Send PIN** within two minutes. The actual PIN stays only in
memory; HA state/history receive a masked placeholder. The button clears the
staged PIN whether sending succeeds or fails.

No OTA will overwrite Matter fabrics, Thread credentials or antenna selection.
Do not erase the entire flash during the USB migration.

This firmware uses a Matter development VID (`0xFFF1`), a test certificate and
a sample serial number. It is **not a production-certified Matter product**.
HTTPS and SHA-256 protect against accidental/corrupted downloads but are not
a substitute for production signing and secure boot.

For release maintainers, see [building and publishing](BOOTSTRAP_AND_OTA.md#building-and-publishing).
