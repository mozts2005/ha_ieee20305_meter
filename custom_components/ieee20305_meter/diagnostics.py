"""Diagnostics support for IEEE 2030.5 integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .const import DATA_COORDINATOR, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry with sensitive fields redacted."""
    data = dict(entry.data)
    for key in ("client_cert", "client_key", "ca_cert"):
        if key in data:
            data[key] = "REDACTED"

    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    device_registry = async_get_device_registry(hass)

    return {
        "entry": data,
        "last_update_success": coordinator.last_update_success,
        "lfdi": coordinator.lfdi,
        "known_devices": len(device_registry.devices),
    }
