"""Coordinator for IEEE 2030.5 telemetry polling."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .certs import compute_lfdi
from .ieee20305_client import IEEE20305Client, IEEE20305ClientConfig

from .const import (
    CONF_AGENT_VERSION,
    CONF_CA_CERT,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_ENDPOINT,
    CONF_METER_HOST,
    CONF_MODE,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Maximum backoff time in seconds (15 minutes)
MAX_BACKOFF_SECONDS = 900


def _entry_value(entry: ConfigEntry, key: str, default: Any = None) -> Any:
    """Get config value from entry options (overrides) or data."""
    return entry.options.get(key, entry.data.get(key, default))


def _get_device_name(entry: ConfigEntry) -> str:
    """Get a human-readable device name from entry config."""
    meter_host = _entry_value(entry, CONF_METER_HOST, "unknown")
    return f"{DOMAIN} - {meter_host}"


class IEEE20305DataUpdateCoordinator(DataUpdateCoordinator[dict[str, float | None]]):
    """Coordinate periodic updates from an IEEE 2030.5 endpoint.

    Each meter device has its own coordinator instance with device-specific
    certificate configuration, allowing independent polling and error handling
    per meter. Implements exponential backoff on connection failures, up to a
    maximum of 15 minutes, at which point the device is marked as in error state.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator for a specific meter device."""
        self._base_poll_seconds = _entry_value(entry, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        device_name = _get_device_name(entry)

        super().__init__(
            hass,
            _LOGGER,
            name=device_name,
            update_interval=timedelta(seconds=self._base_poll_seconds),
        )
        self._entry = entry

        # Backoff tracking
        self._failed_attempts = 0
        self._in_error_state = False

        # Create client with device-specific certificate configuration
        config = IEEE20305ClientConfig(
            endpoint=_entry_value(entry, CONF_ENDPOINT),
            client_cert=_entry_value(entry, CONF_CLIENT_CERT),
            client_key=_entry_value(entry, CONF_CLIENT_KEY),
            ca_cert=_entry_value(entry, CONF_CA_CERT),
            mode=_entry_value(entry, CONF_MODE),
            agent_version=_entry_value(entry, CONF_AGENT_VERSION),
        )
        self._client = IEEE20305Client(config=config)

        # Compute LFDI from this device's certificate
        self.lfdi = compute_lfdi(_entry_value(entry, CONF_CLIENT_CERT))

    @property
    def in_error_state(self) -> bool:
        """Return whether this meter is in an error state due to max backoff."""
        return self._in_error_state

    def _calculate_next_update_interval(self) -> timedelta:
        """Calculate the next update interval based on backoff strategy.

        Uses incremental backoff: base_interval * (failed_attempts + 1)
        Up to a maximum of 15 minutes.
        """
        backoff_seconds = self._base_poll_seconds * (self._failed_attempts + 1)
        backoff_seconds = min(backoff_seconds, MAX_BACKOFF_SECONDS)
        return timedelta(seconds=backoff_seconds)

    async def _async_update_data(self) -> dict[str, float | None]:
        """Fetch telemetry data from the meter."""
        try:
            telemetry = await self._client.fetch_telemetry()

            # Reset backoff on successful connection
            if self._failed_attempts > 0:
                _LOGGER.info(
                    "Device %s: Connection restored after %d failed attempt(s). "
                    "Resuming normal polling.",
                    _entry_value(self._entry, CONF_METER_HOST, "unknown"),
                    self._failed_attempts,
                )
                self._failed_attempts = 0
                self._in_error_state = False
                self.update_interval = timedelta(seconds=self._base_poll_seconds)

            return telemetry.to_dict()

        except Exception as err:  # pragma: no cover
            meter_host = _entry_value(self._entry, CONF_METER_HOST, "unknown")
            self._failed_attempts += 1
            next_interval = self._calculate_next_update_interval()
            next_interval_secs = next_interval.total_seconds()

            # Check if we've reached maximum backoff
            if next_interval_secs >= MAX_BACKOFF_SECONDS:
                self._in_error_state = True
                _LOGGER.error(
                    "Device %s: Connection failed %d times. "
                    "Entered error state (max backoff reached: %d seconds / 15 minutes). "
                    "LFDI=%s. Verify this LFDI is registered in the Energy Providers portal. "
                    "Error: %s",
                    meter_host,
                    self._failed_attempts,
                    int(next_interval_secs),
                    self.lfdi,
                    err,
                )
            else:
                _LOGGER.warning(
                    "Device %s: Connection failed (attempt %d). "
                    "Applying backoff: next retry in %d seconds. "
                    "LFDI=%s. Error: %s",
                    meter_host,
                    self._failed_attempts,
                    int(next_interval_secs),
                    self.lfdi,
                    err,
                )

            # Update the polling interval for next attempt
            self.update_interval = next_interval

            # Raise UpdateFailed to signal coordinator of failure
            raise UpdateFailed(
                f"Unable to fetch IEEE 2030.5 telemetry from {meter_host}: {err}. "
                f"Configured LFDI={self.lfdi}. "
                f"Connection attempt #{self._failed_attempts}. "
                f"{'Entered error state - max backoff reached' if self._in_error_state else f'Next retry in {int(next_interval_secs)} seconds'}. "
                f"Verify LFDI is registered in the Energy Providers portal."
            ) from err
