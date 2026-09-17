# IR Power Meter — Matter over Thread for XIAO ESP32-C6

IR SML reader with Matter energy and power measurements, PIN input,
physical-meter diagnostics, and a Home Assistant companion update entity.
Firmware source is in [`firmware/`](firmware/); the HA custom integration is
in [`custom_components/smartmeter_pin/`](custom_components/smartmeter_pin/).

The first release (`v1.7`) is a **USB-only migration**. It adds a persistent
antenna setting, updated partition table, and bootloader rollback. It cannot
safely be installed over Thread from older v1.6 firmware. Flash it once for
your internal/external antenna using the [migration guide](BOOTSTRAP_AND_OTA.md).
The next release (`v1.8`, numeric Matter version 9) can then be installed via
the companion **Github OTA Firmware** entity in Home Assistant. Nothing installs
automatically. The v1.8 source is in development; a published, compatible
release is required before HA offers Install.

The companion integration reads meter power, diagnostics, and firmware version
together every 30 seconds. It provides a Power sensor even if HA missed its native Matter Power
entity during initial discovery. To enter a PIN, set the **Meter PIN** field,
then press **Send Meter PIN** within two minutes. The actual PIN stays only in
memory; HA state/history receive a masked placeholder. The button clears the
staged PIN whether sending succeeds or fails.

No OTA will overwrite Matter fabrics, Thread credentials or antenna selection.
Do not erase the entire flash during the USB migration.

This firmware uses a Matter development VID (`0xFFF1`), a test certificate and
a sample serial number. It is **not a production-certified Matter product**.
HTTPS and SHA-256 protect against accidental/corrupted downloads but are not
a substitute for production signing and secure boot.

For release maintainers, see [building and publishing](BOOTSTRAP_AND_OTA.md#building-and-publishing).
