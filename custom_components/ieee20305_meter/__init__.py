"""Home Assistant integration setup for IEEE 2030.5 meter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .certs import async_ensure_certificates
from .const import DATA_COORDINATOR, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _entry_config(entry: ConfigEntry) -> dict[str, Any]:
    data = dict(entry.data)
    data.update(entry.options)
    return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from a config entry."""
    from homeassistant.const import Platform
    from .coordinator import IEEE20305DataUpdateCoordinator

    platforms: list[Any] = [Platform.SENSOR]

    current_config = _entry_config(entry)
    updated_config = await async_ensure_certificates(hass, current_config)
    if updated_config != current_config:
        if entry.options:
            hass.config_entries.async_update_entry(entry, options=updated_config)
        else:
            hass.config_entries.async_update_entry(entry, data=updated_config)

    coordinator = IEEE20305DataUpdateCoordinator(hass=hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from homeassistant.const import Platform

    platforms: list[Any] = [Platform.SENSOR]
    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
