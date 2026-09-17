# IR Power Meter — Matter over Thread for XIAO ESP32-C6

IR SML reader with Matter energy and power measurements, PIN input,
physical-meter diagnostics, and a Home Assistant companion update entity.
Firmware source is in [`firmware/`](firmware/); the HA custom integration is
in [`custom_components/smartmeter_pin/`](custom_components/smartmeter_pin/).

The first release (`v1.7`) is a **USB-only migration**. It adds a persistent
antenna setting, updated partition table, and bootloader rollback. It cannot
safely be installed over Thread from older v1.6 firmware. Flash it once for
your internal/external antenna using the [migration guide](BOOTSTRAP_AND_OTA.md).
Later versions, including this v1.9 candidate (numeric Matter version 10),
can be installed via the companion **Github OTA Firmware** entity in Home
Assistant once their release assets are published. Nothing installs
automatically; the user must click Install.

The companion integration reads meter diagnostics and firmware version every 30
seconds. Power is exposed only by Home Assistant's native Matter integration;
it remains unknown until the meter sends a valid SML power reading. When adding
the Matter device to Home Assistant for the first time, keep the IR head on the
meter so Power is non-null during discovery. To enter a PIN, set the **Meter PIN** field,
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
