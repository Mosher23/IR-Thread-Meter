"""Explicit, one-shot Send PIN action for the Matter IR head."""

from __future__ import annotations

from chip.clusters import Objects as Clusters
from matter_server.common.models import EventType

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartMeterRuntimeData
from .const import DOMAIN

_CEC_DIGIT_ZERO = 0x20
_CEC_SELECT = 0x00
_CEC_CLEAR = 0x2C


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SendMeterPinButton(entry.runtime_data)])


class SendMeterPinButton(ButtonEntity):
    """Send the staged PIN and clear it, even when transmission fails."""

    _attr_has_entity_name = True
    _attr_name = "Send PIN"
    _attr_icon = "mdi:send"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime: SmartMeterRuntimeData) -> None:
        self._runtime = runtime
        self._attr_unique_id = f"{runtime.node_id}-send-meter-pin"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, runtime.device_id)},
            "name": "IR Smart Meter",
        }
        self._unsub_node = None

    @property
    def available(self) -> bool:
        try:
            return bool(self._runtime.matter_client.get_node(self._runtime.node_id).available)
        except Exception:
            return False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.coordinator.async_add_listener(self._handle_node_update))
        self._unsub_node = self._runtime.matter_client.subscribe_events(
            callback=self._handle_node_update,
            event_filter=EventType.NODE_UPDATED,
            node_filter=self._runtime.node_id,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_node is not None:
            self._unsub_node()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_node_update(self, event: EventType | None = None, data=None) -> None:
        self.async_write_ha_state()

    async def async_press(self) -> None:
        if not self.available:
            raise HomeAssistantError("The meter is offline")
        if self._runtime.pin_send_lock.locked():
            raise HomeAssistantError("A meter PIN is already being sent")
        async with self._runtime.pin_send_lock:
            pin = self._runtime.take_pin()
            if pin is None:
                raise HomeAssistantError("Enter a four-digit PIN first, then press Send PIN within two minutes")
            try:
                await self._send_key(_CEC_CLEAR)
                for digit in pin:
                    await self._send_key(_CEC_DIGIT_ZERO + int(digit))
                await self._send_key(_CEC_SELECT)
            except Exception as err:
                try:
                    await self._send_key(_CEC_CLEAR)
                except Exception:
                    pass
                if isinstance(err, HomeAssistantError):
                    raise HomeAssistantError(str(err)) from err
                raise HomeAssistantError("Could not send the meter PIN") from err

    async def _send_key(self, key_code: int) -> None:
        command = Clusters.KeypadInput.Commands.SendKey(keyCode=key_code)
        response = await self._runtime.matter_client.send_device_command(
            node_id=self._runtime.node_id,
            endpoint_id=self._runtime.endpoint_id,
            command=command,
        )
        status = (
            response.get("status")
            if isinstance(response, dict)
            else getattr(response, "status", None)
        )
        if status is not None:
            status_code = int(status)
            if status_code == 0:
                return
            if status_code == 2:
                raise HomeAssistantError(
                    "The meter PIN transmitter is busy or its input is incomplete"
                )
            raise HomeAssistantError(
                f"The meter rejected a PIN command (status {status_code})"
            )
