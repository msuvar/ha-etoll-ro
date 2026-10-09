"""Calendar: vignette expiry dates and planned platform maintenance."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import EtollConfigEntry, EtollCoordinator
from .entity import EtollAccountEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EtollConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([EtollCalendar(entry.runtime_data)])


class EtollCalendar(EtollAccountEntity, CalendarEntity):
    """All-day event on each vignette's last valid day + maintenance windows."""

    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator: EtollCoordinator) -> None:
        super().__init__(coordinator, "calendar")

    def _events(self) -> list[CalendarEvent]:
        data = self.coordinator.data
        events: list[CalendarEvent] = []
        for v in data.vehicles.values():
            if v.vignette_expires is None:
                continue
            day = dt_util.as_local(v.vignette_expires).date()
            events.append(
                CalendarEvent(
                    start=day,
                    end=day + timedelta(days=1),
                    summary=f"Expiră rovinieta {v.plate}",
                    description=(
                        f"Rovinieta pentru {v.plate} este valabilă până la "
                        f"{dt_util.as_local(v.vignette_expires):%d.%m.%Y %H:%M}."
                    ),
                    uid=f"etoll_vignette_{v.id}_{day.isoformat()}",
                )
            )
        if data.status:
            for s in data.status.schedules:
                if s.start is None or s.status >= 2:
                    continue
                end = s.end if s.end and s.end > s.start else s.start + timedelta(hours=1)
                events.append(
                    CalendarEvent(
                        start=s.start,
                        end=end,
                        summary=f"Mentenanță etoll.ro: {s.name}",
                        description=s.message,
                        uid=f"etoll_maintenance_{s.name}_{s.start.isoformat()}",
                    )
                )
        return events

    @staticmethod
    def _bounds(ev: CalendarEvent) -> tuple[datetime, datetime]:
        return ev.start_datetime_local, ev.end_datetime_local

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        upcoming = [e for e in self._events() if self._bounds(e)[1] > now]
        return min(upcoming, key=lambda e: self._bounds(e)[0], default=None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            e
            for e in self._events()
            if self._bounds(e)[0] < end_date and self._bounds(e)[1] > start_date
        ]
