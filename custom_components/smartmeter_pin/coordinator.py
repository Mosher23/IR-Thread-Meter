"""Fetch meter diagnostics and power in one bounded Matter read."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from matter_server.common.helpers.util import create_attribute_path

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACTIVE_POWER_OBIS_SEEN_ATTRIBUTE_ID,
    DIAGNOSTICS_CLUSTER_ID,
    METER_ID_ATTRIBUTE_ID,
    METER_MANUFACTURER_ATTRIBUTE_ID,
)

_LOGGER = logging.getLogger(__name__)

# Matter Electrical Power Measurement / ActivePower. The value is in mW.
POWER_CLUSTER_ID = 0x0090
ACTIVE_POWER_ATTRIBUTE_ID = 0x0008
POLL_INTERVAL = timedelta(seconds=30)


class SmartMeterCoordinator(DataUpdateCoordinator[dict[str, object]]):
    """Refresh all companion readings together instead of waiting minutes."""

    def __init__(self, hass, matter_client, node_id: int, endpoint_id: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"IR Smart Meter {node_id}",
            update_interval=POLL_INTERVAL,
        )
        self.matter_client = matter_client
        self.node_id = node_id
        self.paths = [
            create_attribute_path(endpoint_id, DIAGNOSTICS_CLUSTER_ID, attribute_id)
            for attribute_id in (
                ACTIVE_POWER_OBIS_SEEN_ATTRIBUTE_ID,
                METER_ID_ATTRIBUTE_ID,
                METER_MANUFACTURER_ATTRIBUTE_ID,
            )
        ]
        self.paths.append(
            create_attribute_path(endpoint_id, POWER_CLUSTER_ID, ACTIVE_POWER_ATTRIBUTE_ID)
        )
        # Basic Information software version and string, for prompt HA update
        # entity refresh after an OTA reboot rather than a multi-minute wait.
        self.paths.extend(("0/40/9", "0/40/10"))

    async def _async_update_data(self) -> dict[str, object]:
        try:
            node = self.matter_client.get_node(self.node_id)
            if not node.available:
                raise UpdateFailed("The Matter meter is offline")
            return await asyncio.wait_for(
                self.matter_client.read_attribute(self.node_id, self.paths), timeout=15
            )
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Could not read meter attributes: {err}") from err
