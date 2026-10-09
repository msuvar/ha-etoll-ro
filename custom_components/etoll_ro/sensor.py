"""Sensors for eToll România."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import EtollConfigEntry, EtollCoordinator
from .entity import EtollAccountEntity, EtollStatusEntity, EtollVehicleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EtollConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            WalletBalanceSensor(coordinator),
            NotificationsSensor(coordinator),
            ActiveServicesSensor(coordinator),
            PlatformStatusSensor(coordinator),
        ]
    )

    known: set[str] = set()

    @callback
    def _add_vehicles() -> None:
        new = [vid for vid in coordinator.data.vehicles if vid not in known]
        if not new:
            return
        known.update(new)
        entities: list[SensorEntity] = []
        for vid in new:
            entities.append(VignetteExpirySensor(coordinator, vid))
            entities.append(VignetteDaysLeftSensor(coordinator, vid))
            entities.append(VinSensor(coordinator, vid))
        async_add_entities(entities)

    _add_vehicles()
    entry.async_on_unload(coordinator.async_add_listener(_add_vehicles))


# ------------------------------ account sensors ------------------------------ #
class WalletBalanceSensor(EtollAccountEntity, SensorEntity):
    """Sold credite TollRo (portofel preplătit)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "RON"
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:wallet"

    def __init__(self, coordinator: EtollCoordinator) -> None:
        super().__init__(coordinator, "wallet_balance")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.wallet_balance

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"active_credit_services": self.coordinator.data.wallet_services}


class NotificationsSensor(EtollAccountEntity, SensorEntity):
    """Număr notificări active în cont."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:bell"

    def __init__(self, coordinator: EtollCoordinator) -> None:
        super().__init__(coordinator, "notifications")

    @property
    def native_value(self) -> int:
        return self.coordinator.data.notifications


class ActiveServicesSensor(EtollAccountEntity, SensorEntity):
    """Număr servicii active (roviniete, credite, tichete...)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:ticket-confirmation"

    def __init__(self, coordinator: EtollCoordinator) -> None:
        super().__init__(coordinator, "active_services")

    @property
    def native_value(self) -> int:
        return sum(self.coordinator.data.active_services.values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {k.lower(): v for k, v in self.coordinator.data.active_services.items()}


# ------------------------------ vehicle sensors ------------------------------ #
class VignetteExpirySensor(EtollVehicleEntity, SensorEntity):
    """Data expirării rovinietei."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: EtollCoordinator, vehicle_id: str) -> None:
        super().__init__(coordinator, vehicle_id, "vignette_expires")

    @property
    def native_value(self) -> datetime | None:
        v = self.vehicle
        return v.vignette_expires if v else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v = self.vehicle
        if v is None:
            return {}
        return {
            "plate_number": v.plate,
            "country": v.country,
            "vin": v.vin,
            "vehicle_type": v.vehicle_type,
            "category": v.category,
            "emission_standard": v.emission_standard,
            "max_authorized_mass_kg": v.mtma,
            "favorite": v.favorite,
            "valid_from": v.vignette_start.isoformat() if v.vignette_start else None,
            "source": v.vignette_source,
        }


class VignetteDaysLeftSensor(EtollVehicleEntity, SensorEntity):
    """Zile rămase până la expirarea rovinietei."""

    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: EtollCoordinator, vehicle_id: str) -> None:
        super().__init__(coordinator, vehicle_id, "vignette_days_left")

    @property
    def native_value(self) -> int | None:
        v = self.vehicle
        if v is None or v.vignette_expires is None:
            return None
        today = dt_util.now().date()
        exp_day = dt_util.as_local(v.vignette_expires).date()
        return max((exp_day - today).days, 0)


class VinSensor(EtollVehicleEntity, SensorEntity):
    """Seria de șasiu (VIN) a vehiculului."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:barcode"

    def __init__(self, coordinator: EtollCoordinator, vehicle_id: str) -> None:
        super().__init__(coordinator, vehicle_id, "vin")

    @property
    def native_value(self) -> str | None:
        v = self.vehicle
        return v.vin if v else None


class PlatformStatusSensor(EtollStatusEntity, SensorEntity):
    """Starea generală a platformei etoll.ro (pagina publică de status)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        "operational",
        "performance_issues",
        "partial_outage",
        "major_outage",
        "maintenance",
    ]
    _attr_icon = "mdi:server-network"

    def __init__(self, coordinator: EtollCoordinator) -> None:
        super().__init__(coordinator, "platform_status")

    @property
    def native_value(self) -> str | None:
        st = self.coordinator.data.status
        return st.summary if st else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self.coordinator.data.status
        if st is None:
            return {}
        attrs: dict[str, Any] = {
            "components": {c.name: c.status_text for c in st.components},
        }
        if st.active_incidents:
            inc = st.active_incidents[0]
            attrs["incident"] = inc.name
            attrs["incident_status"] = inc.status_text
            attrs["incident_message"] = inc.message
            attrs["incident_since"] = inc.occurred.isoformat() if inc.occurred else None
        nxt = sorted(
            (s for s in st.maintenance_now + st.upcoming_maintenance if s.start),
            key=lambda s: s.start,
        )
        if nxt:
            attrs["maintenance"] = nxt[0].name
            attrs["maintenance_start"] = nxt[0].start.isoformat()
            attrs["maintenance_end"] = nxt[0].end.isoformat() if nxt[0].end else None
        return attrs
