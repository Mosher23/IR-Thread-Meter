"""Diagnostic entity for whether active-power OBIS has been received."""

from __future__ import annotations

from typing import Any

from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartMeterRuntimeData
from .const import ACTIVE_POWER_OBIS_SEEN_ATTRIBUTE_ID, DIAGNOSTICS_CLUSTER_ID


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Matter diagnostic binary sensor."""
    async_add_entities([ActivePowerObisSeenSensor(entry.runtime_data)])


class ActivePowerObisSeenSensor(BinarySensorEntity):
    """Show whether a checksum-valid SML frame contained 1-0:16.7.0*255."""

    _attr_has_entity_name = True
    _attr_name = "Active-power OBIS received"
    _attr_icon = "mdi:meter-electric-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: SmartMeterRuntimeData) -> None:
        """Initialize the entity."""
        self._runtime = runtime
        self._attr_unique_id = f"{runtime.node_id}-active-power-obis-seen"
        self._attr_device_info = {
            "identifiers": {("smartmeter_pin", runtime.device_id)},
            "name": "IR Smart Meter PIN",
        }
        self._attribute_path = create_attribute_path(
            runtime.endpoint_id,
            DIAGNOSTICS_CLUSTER_ID,
            ACTIVE_POWER_OBIS_SEEN_ATTRIBUTE_ID,
        )
        self._unsub = None
        self._unsub_node = None

    @property
    def is_on(self) -> bool:
        """Return true only after the meter has sent active-power OBIS."""
        try:
            node = self._runtime.matter_client.get_node(self._runtime.node_id)
        except KeyError:
            return False
        return bool(node.node_data.attributes.get(self._attribute_path, False))

    async def async_added_to_hass(self) -> None:
        """Listen for reports of the vendor diagnostic attribute."""
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
        """Unsubscribe from Matter updates."""
        if self._unsub is not None:
            self._unsub()
        if self._unsub_node is not None:
            self._unsub_node()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self, event: EventType, data: Any = None) -> None:
        """Write state after the Matter client has updated its node data."""
        self.async_write_ha_state()
