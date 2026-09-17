"""Read-only diagnostics identifying the physical meter behind the IR head."""

from __future__ import annotations

from typing import Any

from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartMeterRuntimeData
from .const import (
    DIAGNOSTICS_CLUSTER_ID,
    METER_ID_ATTRIBUTE_ID,
    METER_MANUFACTURER_ATTRIBUTE_ID,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add both SML identity fields to the companion device."""
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
        ]
    )


class MeterIdentitySensor(SensorEntity):
    """Display a validated SML identity value reported over Matter."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, runtime: SmartMeterRuntimeData, attribute_id: int, name: str, icon: str
    ) -> None:
        """Initialize one diagnostic text sensor."""
        self._runtime = runtime
        self._attr_name = name
        self._attr_icon = f"mdi:{icon}"
        self._attr_unique_id = f"{runtime.node_id}-meter-identity-{attribute_id}"
        self._attr_device_info = {
            "identifiers": {("smartmeter_pin", runtime.device_id)},
            "name": "IR Smart Meter PIN",
        }
        self._attribute_path = create_attribute_path(
            runtime.endpoint_id, DIAGNOSTICS_CLUSTER_ID, attribute_id
        )
        self._unsub = None
        self._unsub_node = None

    @property
    def native_value(self) -> str | None:
        """Return unknown until a valid SML frame contains this OBIS field."""
        try:
            node = self._runtime.matter_client.get_node(self._runtime.node_id)
        except KeyError:
            return None
        value = node.node_data.attributes.get(self._attribute_path)
        if isinstance(value, bytes):
            value = value.decode("ascii", errors="replace")
        return value if isinstance(value, str) and value else None

    async def async_added_to_hass(self) -> None:
        """Follow Matter attribute and node updates."""
        await super().async_added_to_hass()
        self._unsub = self._runtime.matter_client.subscribe_events(
            callback=self._handle_update,
            event_filter=EventType.ATTRIBUTE_UPDATED,
            node_filter=self._runtime.node_id,
            attr_path_filter=self._attribute_path,
        )
        self._unsub_node = self._runtime.matter_client.subscribe_events(
            callback=self._handle_update,
            event_filter=EventType.NODE_UPDATED,
            node_filter=self._runtime.node_id,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop following Matter updates."""
        if self._unsub is not None:
            self._unsub()
        if self._unsub_node is not None:
            self._unsub_node()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self, event: EventType, data: Any = None) -> None:
        """Refresh the displayed identity after a Matter report."""
        self.async_write_ha_state()
