"""Pure data helpers (no Home Assistant imports, easy to unit-test)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .const import TOLL_TYPE_PEAJ, TOLL_TYPE_VIGNETTE

_END_KEYS = ("validUntil", "validityEndDate", "endDate", "expirationDate")
_START_KEYS = ("validFrom", "validityStartDate", "startDate")
_BALANCE_KEYS = ("balance", "remainingBalance", "peajBalance")


def parse_dt(value: Any) -> datetime | None:
    """Parse ISO-8601 strings such as 2026-11-28T23:59:59.999+02:00."""
    if not value or not isinstance(value, str):
        return None
    txt = value.strip()
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(txt)
    except ValueError:
        return None


def _first(d: dict, keys: tuple[str, ...]) -> Any:
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return None


def toll_type(toll: dict) -> str:
    return str(toll.get("type") or toll.get("tollType") or "").upper()


def toll_plate(toll: dict) -> str | None:
    plate = toll.get("plateNumber") or toll.get("vehiclePlateNumber")
    if not plate and isinstance(toll.get("vehicle"), dict):
        plate = toll["vehicle"].get("plateNumber")
    return normalize_plate(plate) if plate else None


def normalize_plate(plate: str | None) -> str:
    return "".join(ch for ch in (plate or "").upper() if ch.isalnum())


def toll_end(toll: dict) -> datetime | None:
    return parse_dt(_first(toll, _END_KEYS))


def toll_start(toll: dict) -> datetime | None:
    return parse_dt(_first(toll, _START_KEYS))


def toll_balance(toll: dict) -> float | None:
    val = _first(toll, _BALANCE_KEYS)
    if isinstance(val, dict):  # e.g. {"amount": 12.3, "currency": "RON"}
        val = val.get("amount")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


@dataclass
class VehicleInfo:
    """What the integration exposes for one vehicle."""

    id: str
    plate: str
    country: str | None
    vin: str | None
    vehicle_type: str | None
    category: str | None
    emission_standard: str | None
    mtma: float | None
    favorite: bool
    vignette_expires: datetime | None
    vignette_start: datetime | None = None
    vignette_source: str | None = None  # "vehicle" | "toll"
    eligible_intervals: list = field(default_factory=list)


@dataclass
class EtollData:
    """Snapshot returned by the coordinator."""

    profile_id: str | None
    profile_name: str | None
    vehicles: dict[str, VehicleInfo]
    wallet_balance: float | None
    wallet_services: int
    notifications: int
    active_services: dict[str, int]
    notification_list: list = field(default_factory=list)
    new_notifications: list = field(default_factory=list)
    status: "PlatformStatus | None" = None


def build_data(
    profiles: list[dict],
    vehicles: list[dict],
    tolls: list[dict],
    notifications: int,
) -> EtollData:
    """Combine raw API answers into an EtollData snapshot."""
    current = next((p for p in profiles if p.get("isCurrent")), profiles[0] if profiles else {})

    # Latest-ending active vignette per plate (new-system purchases)
    vignette_by_plate: dict[str, dict] = {}
    for t in tolls:
        if toll_type(t) != TOLL_TYPE_VIGNETTE:
            continue
        plate = toll_plate(t)
        if not plate:
            continue
        prev = vignette_by_plate.get(plate)
        new_end, prev_end = toll_end(t), toll_end(prev) if prev else None
        if prev is None or (new_end is not None and (prev_end is None or new_end > prev_end)):
            vignette_by_plate[plate] = t

    result: dict[str, VehicleInfo] = {}
    for v in vehicles:
        vid = v.get("id")
        if not vid:
            continue
        plate = normalize_plate(v.get("plateNumber"))
        elig = v.get("vignetteEligibility") or {}
        exp = parse_dt(elig.get("expirationDateCurrentVignette"))
        source = "vehicle" if exp else None
        start = None
        toll = vignette_by_plate.get(plate)
        if toll is not None:
            t_end = toll_end(toll)
            if t_end and (exp is None or t_end > exp):
                exp, source = t_end, "toll"
            start = toll_start(toll)
        try:
            mtma = float(v["mtma"]) if v.get("mtma") is not None else None
        except (TypeError, ValueError):
            mtma = None
        result[vid] = VehicleInfo(
            id=vid,
            plate=v.get("plateNumber") or plate,
            country=v.get("countryCode") or v.get("country"),
            vin=v.get("vin") or None,
            vehicle_type=v.get("vehicleType"),
            category=v.get("category"),
            emission_standard=v.get("emissionStandard"),
            mtma=mtma,
            favorite=bool(v.get("favorite")),
            vignette_expires=exp,
            vignette_start=start,
            vignette_source=source,
            eligible_intervals=list(elig.get("eligibleIntervals") or []),
        )

    balance: float | None = None
    wallet_services = 0
    active: dict[str, int] = {}
    for t in tolls:
        tt = toll_type(t) or "UNKNOWN"
        active[tt] = active.get(tt, 0) + 1
        if tt == TOLL_TYPE_PEAJ:
            b = toll_balance(t)
            if b is not None:
                balance = (balance or 0.0) + b
                wallet_services += 1

    return EtollData(
        profile_id=current.get("id"),
        profile_name=current.get("name"),
        vehicles=result,
        wallet_balance=balance if balance is not None else 0.0,
        wallet_services=wallet_services,
        notifications=notifications,
        active_services=active,
    )


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
_NOTIF_ID_KEYS = ("id", "notificationId", "uuid", "guid")
_NOTIF_TYPE_KEYS = ("type", "notificationType", "code", "category", "event")
_NOTIF_TITLE_KEYS = ("title", "subject", "name")
_NOTIF_MSG_KEYS = ("message", "body", "description", "text", "content")
_NOTIF_TIME_KEYS = ("createdAt", "created", "createdDate", "date", "timestamp", "sentAt")


@dataclass
class Notification:
    """One portal notification, normalised."""

    id: str
    type: str
    title: str | None
    message: str | None
    created: datetime | None
    plate: str | None
    raw: dict

    def as_event_data(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "created": self.created.isoformat() if self.created else None,
            "plate_number": self.plate,
        }


def parse_notification(raw: dict) -> Notification | None:
    nid = _first(raw, _NOTIF_ID_KEYS)
    ntype = _first(raw, _NOTIF_TYPE_KEYS)
    if nid is None:
        # fall back to a stable fingerprint
        nid = f"{ntype}|{_first(raw, _NOTIF_TIME_KEYS)}|{_first(raw, _NOTIF_MSG_KEYS)}"
    created = _first(raw, _NOTIF_TIME_KEYS)
    created_dt = parse_dt(created) if isinstance(created, str) else None
    plate = raw.get("plateNumber")
    if not plate and isinstance(raw.get("vehicle"), dict):
        plate = raw["vehicle"].get("plateNumber")
    return Notification(
        id=str(nid),
        type=str(ntype or "OTHER").upper(),
        title=_first(raw, _NOTIF_TITLE_KEYS),
        message=_first(raw, _NOTIF_MSG_KEYS),
        created=created_dt,
        plate=plate,
        raw=raw,
    )


# --------------------------------------------------------------------------- #
# Platform status (Cachet 3 public API)
# --------------------------------------------------------------------------- #
@dataclass
class StatusComponent:
    name: str
    status: int
    status_text: str
    description: str | None


@dataclass
class StatusIncident:
    name: str
    message: str | None
    status: int  # 4 = fixed
    status_text: str
    occurred: datetime | None


@dataclass
class StatusSchedule:
    name: str
    message: str | None
    status: int  # 0 upcoming, 1 in progress, 2 complete
    status_text: str
    start: datetime | None
    end: datetime | None


@dataclass
class PlatformStatus:
    components: list[StatusComponent]
    incidents: list[StatusIncident]
    schedules: list[StatusSchedule]

    @property
    def active_incidents(self) -> list[StatusIncident]:
        return [i for i in self.incidents if i.status < 4]

    @property
    def degraded_components(self) -> list[StatusComponent]:
        return [c for c in self.components if c.status != 1]

    @property
    def maintenance_now(self) -> list[StatusSchedule]:
        return [s for s in self.schedules if s.status == 1]

    @property
    def upcoming_maintenance(self) -> list[StatusSchedule]:
        return [s for s in self.schedules if s.status == 0]

    @property
    def has_problem(self) -> bool:
        return bool(self.degraded_components or self.active_incidents or self.maintenance_now)

    @property
    def summary(self) -> str:
        if self.maintenance_now:
            return "maintenance"
        if not self.degraded_components and not self.active_incidents:
            return "operational"
        worst = max((c.status for c in self.degraded_components), default=2)
        return {2: "performance_issues", 3: "partial_outage", 4: "major_outage"}.get(
            worst, "maintenance" if worst >= 5 else "performance_issues"
        )


def _cachet_dt(block: Any, tz) -> datetime | None:
    if not isinstance(block, dict) or not block.get("string"):
        return None
    try:
        return datetime.strptime(block["string"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
    except ValueError:
        return None


def _cachet_status(block: Any) -> tuple[int, str]:
    if isinstance(block, dict):
        try:
            return int(block.get("value", 0)), str(block.get("human") or "")
        except (TypeError, ValueError):
            pass
    return 0, ""


def build_status(raw: dict[str, list[dict]], tz) -> PlatformStatus:
    comps = []
    for c in raw.get("components", []):
        if c.get("enabled") is False:
            continue
        val, txt = _cachet_status(c.get("latest_status") or c.get("status"))
        comps.append(StatusComponent(c.get("name") or "?", val, txt, c.get("description") or None))
    incs = []
    for i in raw.get("incidents", []):
        if i.get("visible") in (0, False):
            continue
        val, txt = _cachet_status(i.get("status"))
        incs.append(StatusIncident(i.get("name", "").strip(), i.get("message"), val, txt, _cachet_dt(i.get("occurred"), tz)))
    scheds = []
    for s in raw.get("schedules", []):
        val, txt = _cachet_status(s.get("status"))
        scheds.append(
            StatusSchedule(
                s.get("name", "").strip(), s.get("message"), val, txt,
                _cachet_dt(s.get("scheduled"), tz), _cachet_dt(s.get("completed"), tz),
            )
        )
    return PlatformStatus(comps, incs, scheds)
