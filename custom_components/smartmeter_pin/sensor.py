"""Read-only diagnostics identifying the physical meter behind the IR head."""

from __future__ import annotations

from matter_server.common.helpers.util import create_attribute_path

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SmartMeterRuntimeData
from .coordinator import ACTIVE_POWER_ATTRIBUTE_ID, POWER_CLUSTER_ID
from .const import (
    DIAGNOSTICS_CLUSTER_ID,
    METER_ID_ATTRIBUTE_ID,
    METER_MANUFACTURER_ATTRIBUTE_ID,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add SML identity fields and a direct standard Matter Power sensor."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            MeterIdentitySensor(runtime, METER_ID_ATTRIBUTE_ID, "Meter ID", "identifier"),
            MeterIdentitySensor(
                runtime,
                METER_MANUFACTURER_ATTRIBUTE_ID,
                "Meter manufacturer",
                "factory",
            ),
            MeterActivePowerSensor(runtime),
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


class MeterActivePowerSensor(CoordinatorEntity, SensorEntity):
    """Expose ActivePower even if HA skipped native Matter discovery."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_icon = "mdi:flash"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_suggested_display_precision = 1

    def __init__(self, runtime: SmartMeterRuntimeData) -> None:
        super().__init__(runtime.coordinator)
        self._attr_unique_id = f"{runtime.node_id}-meter-active-power"
        self._attr_device_info = {
            "identifiers": {("smartmeter_pin", runtime.device_id)},
            "name": "IR Smart Meter",
        }
        self._attribute_path = create_attribute_path(
            runtime.endpoint_id, POWER_CLUSTER_ID, ACTIVE_POWER_ATTRIBUTE_ID
        )

    @property
    def native_value(self) -> float | None:
        """Matter power is signed milliwatts; Home Assistant displays watts."""
        value = (self.coordinator.data or {}).get(self._attribute_path)
        if type(value) is not int:
            return None
        return value / 1000
