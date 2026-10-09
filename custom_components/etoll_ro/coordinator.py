"""DataUpdateCoordinator for eToll România."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EtollApiClient, EtollAuthError, EtollError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN, DOMAIN
from .models import EtollData, build_data

_LOGGER = logging.getLogger(__name__)

type EtollConfigEntry = ConfigEntry["EtollCoordinator"]


class EtollCoordinator(DataUpdateCoordinator[EtollData]):
    """Fetch vehicles, active services and notifications."""

    config_entry: EtollConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: EtollConfigEntry, client: EtollApiClient
    ) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=minutes),
        )
        self.client = client

    async def _async_update_data(self) -> EtollData:
        try:
            profiles = await self.client.async_get_profiles()
            vehicles, tolls, notifications = await asyncio.gather(
                self.client.async_get_vehicles(),
                self.client.async_get_active_tolls(),
                self.client.async_get_notification_count(),
            )
        except EtollAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EtollError as err:
            raise UpdateFailed(str(err)) from err
        return build_data(profiles, vehicles, tolls, notifications)
