"""DataUpdateCoordinator for eToll România."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EtollApiClient, EtollAuthError, EtollError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    EVENT_NOTIFICATION,
    STATUS_TZ,
)
from .models import EtollData, PlatformStatus, build_data, build_status, parse_notification

_LOGGER = logging.getLogger(__name__)

type EtollConfigEntry = ConfigEntry["EtollCoordinator"]


class EtollCoordinator(DataUpdateCoordinator[EtollData]):
    """Fetch vehicles, active services, notifications and platform status."""

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
        self._seen_notifications: set[str] | None = None  # None = first run
        self._last_status: PlatformStatus | None = None
        self._status_tz = ZoneInfo(STATUS_TZ)

    async def _async_update_data(self) -> EtollData:
        try:
            profiles = await self.client.async_get_profiles()
            vehicles, tolls, count, notif_raw = await asyncio.gather(
                self.client.async_get_vehicles(),
                self.client.async_get_active_tolls(),
                self.client.async_get_notification_count(),
                self.client.async_get_notifications(),
            )
        except EtollAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EtollError as err:
            raise UpdateFailed(str(err)) from err

        # The public status page is optional – never fail the update because of it.
        try:
            status = build_status(await self.client.async_get_status(), self._status_tz)
            self._last_status = status
        except EtollError as err:
            _LOGGER.debug("Status page unavailable: %s", err)
            status = self._last_status

        data = build_data(profiles, vehicles, tolls, count)
        data.status = status
        data.notification_list = [n for n in map(parse_notification, notif_raw) if n]

        ids = {n.id for n in data.notification_list}
        if self._seen_notifications is None:
            # First refresh after start-up: remember, don't replay old notifications.
            self._seen_notifications = ids
        else:
            data.new_notifications = [
                n for n in data.notification_list if n.id not in self._seen_notifications
            ]
            self._seen_notifications |= ids
            for notif in data.new_notifications:
                self.hass.bus.async_fire(
                    EVENT_NOTIFICATION,
                    {"config_entry_id": self.config_entry.entry_id, **notif.as_event_data()},
                )
        return data
