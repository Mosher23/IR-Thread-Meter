"""Read-only diagnostics identifying the physical meter behind the IR head."""

from __future__ import annotations

from matter_server.common.helpers.util import create_attribute_path

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SmartMeterRuntimeData
from .const import (
    DIAGNOSTICS_CLUSTER_ID,
    DOMAIN,
    METER_ID_ATTRIBUTE_ID,
    METER_MANUFACTURER_ATTRIBUTE_ID,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add SML identity fields; power is provided by the Matter integration."""
    runtime = entry.runtime_data
    registry = er.async_get(hass)
    legacy_power_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{runtime.node_id}-meter-active-power"
    )
    if legacy_power_id is not None:
        legacy_power = registry.async_get(legacy_power_id)
        if legacy_power is not None and legacy_power.config_entry_id == entry.entry_id:
            registry.async_remove(legacy_power_id)
    async_add_entities(
        [
            MeterIdentitySensor(runtime, METER_ID_ATTRIBUTE_ID, "Meter ID", "identifier"),
            MeterIdentitySensor(
                runtime,
                METER_MANUFACTURER_ATTRIBUTE_ID,
                "Meter manufacturer",
                "factory",
            ),
        ]
    )


class MeterIdentitySensor(CoordinatorEntity, SensorEntity):
    """Display a validated SML identity value reported over Matter."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, runtime: SmartMeterRuntimeData, attribute_id: int, name: str, icon: str
    ) -> None:
        """Initialize one diagnostic text sensor."""
        super().__init__(runtime.coordinator)
        self._runtime = runtime
        self._attr_name = name
        self._attr_icon = f"mdi:{icon}"
        self._attr_unique_id = f"{runtime.node_id}-meter-identity-{attribute_id}"
        self._attr_device_info = {
            "identifiers": {("smartmeter_pin", runtime.device_id)},
            "name": "IR Smart Meter",
        }
        self._attribute_path = create_attribute_path(
            runtime.endpoint_id, DIAGNOSTICS_CLUSTER_ID, attribute_id
        )

    @property
    def native_value(self) -> str | None:
        """Return unknown until a valid SML frame contains this OBIS field."""
        value = (self.coordinator.data or {}).get(self._attribute_path)
        if isinstance(value, bytes):
            value = value.decode("ascii", errors="replace")
        return value if isinstance(value, str) and value else None
