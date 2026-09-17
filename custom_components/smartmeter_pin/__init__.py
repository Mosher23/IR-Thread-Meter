"""IR Smart Meter PIN custom integration."""

from __future__ import annotations

from dataclasses import dataclass

from chip.clusters import Objects as Clusters

from homeassistant.components.matter.helpers import (
    get_matter,
    node_from_ha_device_id,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DEVICE_ID

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.TEXT, Platform.UPDATE]


@dataclass
class SmartMeterRuntimeData:
    """Matter objects used by the integration's entities."""

    matter_client: object
    node_id: int
    endpoint_id: int
    device_id: str


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PIN entry and diagnostics for the selected Matter meter."""
    node = node_from_ha_device_id(hass, entry.data[CONF_DEVICE_ID])
    if node is None:
        raise ConfigEntryNotReady("The selected Matter device is not available")

    endpoint = next(
        (
            endpoint
            for endpoint in node.endpoints.values()
            if endpoint.has_cluster(Clusters.KeypadInput)
        ),
        None,
    )
    if endpoint is None:
        raise ConfigEntryNotReady(
            "The selected device does not expose the Smart Meter Keypad Input cluster"
        )

    matter_client = get_matter(hass).matter_client
    if matter_client.server_info is None:
        raise ConfigEntryNotReady("Matter server information is not available")

    entry.runtime_data = SmartMeterRuntimeData(
        matter_client=matter_client,
        node_id=node.node_id,
        endpoint_id=endpoint.endpoint_id,
        device_id=entry.data[CONF_DEVICE_ID],
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
