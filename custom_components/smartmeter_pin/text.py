"""Password-style field that stages a meter PIN for the Send button."""

from __future__ import annotations

from matter_server.common.models import EventType

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartMeterRuntimeData

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the non-persistent PIN-entry field."""
    async_add_entities([MeterPinTextEntity(entry.runtime_data)])


class MeterPinTextEntity(TextEntity):
    """Hold four digits in memory, never in Home Assistant state/history."""

    _attr_has_entity_name = True
    _attr_name = "Meter PIN"
    _attr_icon = "mdi:form-textbox-password"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.PASSWORD
    # The entity is intentionally cleared after every submission. Its minimum
    # therefore has to permit the empty idle state; exact four-digit validation
    # remains enforced in async_set_value().
    _attr_native_min = 0
    _attr_native_max = 4
    _attr_native_value = ""

    def __init__(self, runtime: SmartMeterRuntimeData) -> None:
        """Initialize the entity."""
        self._runtime = runtime
        self._attr_unique_id = f"{runtime.node_id}-meter-pin"
        self._attr_device_info = {
            "identifiers": {("smartmeter_pin", runtime.device_id)},
            "name": "IR Smart Meter PIN",
        }
        self._unsub_node = None
        runtime.clear_pin_display = self._clear_input

    @property
    def available(self) -> bool:
        """Disable PIN entry while the Matter node is disconnected."""
        try:
            return bool(self._runtime.matter_client.get_node(self._runtime.node_id).available)
        except Exception:
            return False

    async def async_added_to_hass(self) -> None:
        """Refresh availability whenever the Matter node reconnects."""
        await super().async_added_to_hass()
        self._unsub_node = self._runtime.matter_client.subscribe_events(
            callback=self._handle_node_update,
            event_filter=EventType.NODE_UPDATED,
            node_filter=self._runtime.node_id,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from Matter updates."""
        if self._unsub_node is not None:
            self._unsub_node()
        if self._runtime.clear_pin_display == self._clear_input:
            self._runtime.clear_pin_display = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_node_update(self, event: EventType, data=None) -> None:
        """Write state after a Matter availability update."""
        self.async_write_ha_state()

    async def async_set_value(self, value: str) -> None:
        """Stage a PIN; the separate button performs optical transmission."""
        if len(value) != 4 or not value.isdecimal() or value == "0000":
            raise HomeAssistantError("Enter a valid four-digit meter PIN")
        self._runtime.stage_pin(value)
        # Only a non-secret placeholder ever enters the HA state machine.
        self._attr_native_value = "••••"
        self.async_write_ha_state()

    @callback
    def _clear_input(self) -> None:
        self._attr_native_value = ""
        self.async_write_ha_state()
