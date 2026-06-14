"""Home Assistant integration setup for IEEE 2030.5 meter."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .certs import (
    async_ensure_certificates,
    async_has_deprecated_certificate_paths,
    async_migrate_legacy_certificate_paths,
)
from .const import DATA_COORDINATOR, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Signal for error state changes
SIGNAL_METER_ERROR_STATE_CHANGED = f"{DOMAIN}_error_state_changed"


def _entry_config(entry: ConfigEntry) -> dict[str, Any]:
    """Build complete config from entry data and options.

    Options override data, allowing runtime configuration changes.
    """
    data = dict(entry.data)
    data.update(entry.options)
    return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from a config entry.

    Each meter device gets its own independent certificate configuration.
    Certificates are generated per-device to support multiple meters
    with different endpoints and credentials.
    """
    from homeassistant.const import Platform
    from .coordinator import IEEE20305DataUpdateCoordinator

    platforms: list[Any] = [Platform.SENSOR]

    current_config = _entry_config(entry)

    # One-time in-place migration for legacy shared certificate paths.
    current_config = await async_migrate_legacy_certificate_paths(hass, current_config)

    # Ensure certificates exist for this specific device
    # Each meter gets its own CA and client certificates
    updated_config = await async_ensure_certificates(hass, current_config)

    if updated_config != current_config:
        # Update entry with resolved certificate paths
        if entry.options:
            hass.config_entries.async_update_entry(entry, options=updated_config)
        else:
            hass.config_entries.async_update_entry(entry, data=updated_config)

    # If deprecated cert values still remain, notify user to reconfigure.
    if await async_has_deprecated_certificate_paths(hass, updated_config):
        _create_deprecated_config_notification(hass, entry)

    # Create data update coordinator for this meter device
    coordinator = IEEE20305DataUpdateCoordinator(hass=hass, entry=entry)

    # Attempt first refresh, but allow setup to continue even if meter is unreachable
    # LFDI is always available from certificate, regardless of connectivity
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # pragma: no cover
        meter_host = _entry_config(entry).get("meter_host", "unknown")
        _LOGGER.warning(
            "First update failed for meter at %s; LFDI will still be available: %s",
            meter_host,
            err,
        )

    # Store coordinator per entry (each device has its own coordinator)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_COORDINATOR: coordinator}

    # Set up sensor platforms for this device
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Check if coordinator is already in error state at startup
    if coordinator.in_error_state:
        _create_error_notification(hass, entry, coordinator)

    return True


def _create_error_notification(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: Any
) -> None:
    """Create a persistent notification when meter enters error state.

    Alerts the administrator that a meter has reached maximum backoff
    and is not connecting.
    """
    from homeassistant.components import persistent_notification

    meter_host = _entry_config(entry).get("meter_host", "unknown")
    meter_port = _entry_config(entry).get("meter_port", 8081)

    notification_id = f"{DOMAIN}_{entry.entry_id}_error_state"
    title = f"IEEE 2030.5 Meter Connection Error: {meter_host}"
    message = (
        f"Meter at **{meter_host}:{meter_port}** has failed to connect after multiple retry attempts "
        f"and has entered an error state.\n\n"
        f"**Configured LFDI:** `{coordinator.lfdi}`\n\n"
        f"**Actions to take:**\n"
        f"1. Verify the meter is powered on and connected to the network\n"
        f"2. Check that the IP address and port are correct\n"
        f"3. Ensure the LFDI is registered in the Energy Provider's portal\n"
        f"4. Check firewall settings to allow mTLS connections (port {meter_port})\n"
        f"5. Review the Home Assistant logs for detailed error messages\n\n"
        f"The integration will continue retrying with a 15-minute interval. "
        f"Once the meter is accessible, the connection will be restored automatically."
    )

    persistent_notification.create(
        hass,
        message,
        title,
        notification_id,
    )

    _LOGGER.error(
        "Meter at %s:%s entered error state. "
        "Created notification for administrator. LFDI=%s",
        meter_host,
        meter_port,
        coordinator.lfdi,
    )


def _create_deprecated_config_notification(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Notify user that legacy shared certificate paths are deprecated."""
    from homeassistant.components import persistent_notification

    meter_host = _entry_config(entry).get("meter_host", "unknown")
    notification_id = f"{DOMAIN}_{entry.entry_id}_deprecated_cert_config"
    title = f"IEEE 2030.5 Meter Deprecated Certificate Config: {meter_host}"
    message = (
        "This meter entry still references a deprecated shared certificate layout under "
        "`ieee20305_meter/certs`.\n\n"
        "The integration now expects per-device certificate paths and attempted automatic migration. "
        "Please open the integration options and save settings to refresh paths, or reconfigure "
        "certificate files manually if needed."
    )

    persistent_notification.create(hass, message, title, notification_id)

    _LOGGER.warning(
        "Meter at %s is using deprecated shared certificate configuration paths.",
        meter_host,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from homeassistant.const import Platform

    platforms: list[Any] = [Platform.SENSOR]
    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
