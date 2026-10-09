"""Base entities for eToll România."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, PORTAL_URL
from .coordinator import EtollCoordinator
from .models import VehicleInfo


class EtollAccountEntity(CoordinatorEntity[EtollCoordinator]):
    """Entity attached to the account device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EtollCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account_{entry.unique_id}")},
            name=f"eToll {coordinator.data.profile_name or entry.title}",
            manufacturer=MANUFACTURER,
            model="Cont TollRo",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{PORTAL_URL}/portal-extern/profile",
        )


class EtollVehicleEntity(CoordinatorEntity[EtollCoordinator]):
    """Entity attached to one vehicle device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EtollCoordinator, vehicle_id: str, key: str) -> None:
        super().__init__(coordinator)
        self.vehicle_id = vehicle_id
        v = coordinator.data.vehicles[vehicle_id]
        self._attr_unique_id = f"{vehicle_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle_id)},
            name=v.plate,
            serial_number=v.vin,
            manufacturer=MANUFACTURER,
            model=f"Vehicul {v.vehicle_type or ''} cat. {v.category or '?'}".strip(),
            via_device=(DOMAIN, f"account_{coordinator.config_entry.unique_id}"),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{PORTAL_URL}/portal-extern/profile",
        )

    @property
    def vehicle(self) -> VehicleInfo | None:
        return self.coordinator.data.vehicles.get(self.vehicle_id)

    @property
    def available(self) -> bool:
        return super().available and self.vehicle is not None
