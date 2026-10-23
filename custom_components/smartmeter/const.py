"""Constants for the SML over Matter/Thread integration."""

from __future__ import annotations

NAME = "SML over Matter/Thread"
DOMAIN = "smartmeter"
CONF_DEVICE_ID = "device_id"
INTEGRATION_VERSION = "2.1.5"
PROJECT_URL = "https://github.com/Mosher23/SML-over-Matter-Thread"


def companion_device_info(device_id: str) -> dict:
    """Describe the HA companion, not the XIAO's separate Matter device."""
    return {
        "identifiers": {(DOMAIN, device_id)},
        "name": NAME,
        "manufacturer": "Mosher23",
        "model": "Home Assistant companion integration",
        "sw_version": INTEGRATION_VERSION,
        "configuration_url": PROJECT_URL,
    }


def normalize_legacy_name(name: str | None) -> str | None:
    """Update default project names while preserving custom names."""
    if name in {"IR Smart Meter", "IR Smart Meter PIN"}:
        return NAME
    if name == "Smart Meter PIN":
        return "Smart Meter"
    return name


# Matter MEI vendor cluster exposed by firmware v1.4 and later. The low
# 16-bit cluster suffix must be in Matter's manufacturer-specific range.
DIAGNOSTICS_CLUSTER_ID = 0xFFF1FC01
ACTIVE_POWER_OBIS_SEEN_ATTRIBUTE_ID = 0x00000000
METER_ID_ATTRIBUTE_ID = 0x00000001
METER_MANUFACTURER_ATTRIBUTE_ID = 0x00000002
EXTERNAL_ANTENNA_ATTRIBUTE_ID = 0x00000003
ON_OFF_CLUSTER_ID = 0x0006
ON_OFF_ATTRIBUTE_ID = 0x0000
