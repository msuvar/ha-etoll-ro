"""Binary sensors for eToll România."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import EtollConfigEntry, EtollCoordinator
from .entity import EtollVehicleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EtollConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_vehicles() -> None:
        new = [vid for vid in coordinator.data.vehicles if vid not in known]
        if not new:
            return
        known.update(new)
        async_add_entities(VignetteValidBinarySensor(coordinator, vid) for vid in new)

    _add_vehicles()
    entry.async_on_unload(coordinator.async_add_listener(_add_vehicles))


class VignetteValidBinarySensor(EtollVehicleEntity, BinarySensorEntity):
    """On = rovinietă valabilă acum."""

    def __init__(self, coordinator: EtollCoordinator, vehicle_id: str) -> None:
        super().__init__(coordinator, vehicle_id, "vignette_valid")

    @property
    def is_on(self) -> bool | None:
        v = self.vehicle
        if v is None:
            return None
        if v.vignette_expires is None:
            return False
        # A renewal bought in advance (start in the future) normally follows a
        # still-valid vignette, so only the end date is checked.
        return v.vignette_expires >= dt_util.utcnow()

    @property
    def icon(self) -> str:
        return "mdi:check-decagram" if self.is_on else "mdi:alert-decagram"
