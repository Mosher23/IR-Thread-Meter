"""Password-style Home Assistant text entity for meter PIN entry."""

from __future__ import annotations

from chip.clusters import Objects as Clusters
from matter_server.common.models import EventType

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartMeterRuntimeData

# CEC Key Code values used by the standard Matter Keypad Input cluster.
_CEC_DIGIT_ZERO = 0x20
_CEC_SELECT = 0x00
_CEC_CLEAR = 0x2C


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the non-persistent PIN-entry field."""
    async_add_entities([MeterPinTextEntity(entry.runtime_data)])


class MeterPinTextEntity(TextEntity):
    """Send exactly four digits over Matter Keypad Input, then clear the UI."""

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
        await super().async_will_remove_from_hass()

    @callback
    def _handle_node_update(self, event: EventType, data=None) -> None:
        """Write state after a Matter availability update."""
        self.async_write_ha_state()

    async def async_set_value(self, value: str) -> None:
        """Transmit a four-digit PIN without retaining it in Home Assistant."""
        if len(value) != 4 or not value.isdecimal() or value == "0000":
            raise HomeAssistantError("Enter a valid four-digit meter PIN")

        try:
            # Clear a partial entry left by any interrupted prior request.
            await self._send_key(_CEC_CLEAR)
            for digit in value:
                await self._send_key(_CEC_DIGIT_ZERO + int(digit))
            await self._send_key(_CEC_SELECT)
        except Exception as err:
            try:
                await self._send_key(_CEC_CLEAR)
            except Exception:  # Best effort only; retain the original error.
                pass
            raise HomeAssistantError("Could not send the meter PIN") from err
        finally:
            # Do not persist or display the PIN after it has been sent.
            self._attr_native_value = ""
            self.async_write_ha_state()

    async def _send_key(self, key_code: int) -> None:
        """Send one standard Keypad Input command."""
        command = Clusters.KeypadInput.Commands.SendKey(keyCode=key_code)
        await self._runtime.matter_client.send_device_command(
            node_id=self._runtime.node_id,
            endpoint_id=self._runtime.endpoint_id,
            command=command,
        )
