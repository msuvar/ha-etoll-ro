"""Event entity: one event per new eToll notification."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import NOTIFICATION_TYPES
from .coordinator import EtollConfigEntry, EtollCoordinator
from .entity import EtollAccountEntity

PARALLEL_UPDATES = 0

_TYPES = [t.lower() for t in NOTIFICATION_TYPES]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EtollConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([NotificationEvent(entry.runtime_data)])


class NotificationEvent(EtollAccountEntity, EventEntity):
    """Fires for every notification that appears in the eToll account."""

    _attr_event_types = _TYPES
    _attr_icon = "mdi:bell-ring"

    def __init__(self, coordinator: EtollCoordinator) -> None:
        super().__init__(coordinator, "notification")

    @callback
    def _handle_coordinator_update(self) -> None:
        for notif in self.coordinator.data.new_notifications:
            etype = notif.type.lower()
            if etype not in _TYPES:
                etype = "other"
            self._trigger_event(etype, notif.as_event_data())
        super()._handle_coordinator_update()
