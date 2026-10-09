"""Diagnostics for eToll România (sensitive data redacted)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import EtollConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, "profile_name", "plate", "vin", "id", "profile_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EtollConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    snapshot = asdict(data)
    snapshot["vehicles"] = [
        async_redact_data(v, TO_REDACT) for v in snapshot["vehicles"].values()
    ]
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "data": async_redact_data(snapshot, TO_REDACT),
    }
