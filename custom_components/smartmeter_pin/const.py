"""Constants for the IR Smart Meter integration."""

from __future__ import annotations

DOMAIN = "smartmeter_pin"
CONF_DEVICE_ID = "device_id"


def normalize_legacy_name(name: str | None) -> str | None:
    """Drop PIN from names used by older versions of this integration."""
    if name == "IR Smart Meter PIN":
        return "IR Smart Meter"
    if name == "Smart Meter PIN":
        return "Smart Meter"
    return name


# Matter MEI vendor cluster exposed by firmware v1.4 and later. The low
# 16-bit cluster suffix must be in Matter's manufacturer-specific range.
DIAGNOSTICS_CLUSTER_ID = 0xFFF1FC01
ACTIVE_POWER_OBIS_SEEN_ATTRIBUTE_ID = 0x00000000
METER_ID_ATTRIBUTE_ID = 0x00000001
METER_MANUFACTURER_ATTRIBUTE_ID = 0x00000002
