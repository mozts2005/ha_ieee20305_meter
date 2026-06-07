"""Coordinator for IEEE 2030.5 telemetry polling."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .certs import compute_lfdi
from .ieee20305_client import IEEE20305Client, IEEE20305ClientConfig

from .const import (
    CONF_CA_CERT,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_ENDPOINT,
    CONF_MODE,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class IEEE20305DataUpdateCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Coordinate periodic updates from an IEEE 2030.5 endpoint."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        poll_seconds = entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_seconds),
        )
        self._entry = entry

        config = IEEE20305ClientConfig(
            endpoint=entry.data[CONF_ENDPOINT],
            client_cert=entry.data[CONF_CLIENT_CERT],
            client_key=entry.data[CONF_CLIENT_KEY],
            ca_cert=entry.data[CONF_CA_CERT],
            mode=entry.data[CONF_MODE],
        )
        self._client = IEEE20305Client(config=config)
        self.lfdi = compute_lfdi(entry.data[CONF_CLIENT_CERT])

    async def _async_update_data(self) -> dict[str, float]:
        try:
            telemetry = await self._client.fetch_telemetry()
            return telemetry.to_dict()
        except Exception as err:  # pragma: no cover
            raise UpdateFailed(f"Unable to fetch IEEE 2030.5 telemetry: {err}") from err
