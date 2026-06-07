"""Minimal async IEEE 2030.5 client for telemetry polling.

This module intentionally uses HTTPS polling and does not support MQTT.
"""

from __future__ import annotations

from dataclasses import dataclass
import ssl
from typing import Any

import aiohttp


@dataclass(frozen=True)
class IEEE20305ClientConfig:
    """Runtime config for connecting to IEEE 2030.5 endpoint."""

    endpoint: str
    client_cert: str
    client_key: str
    ca_cert: str
    mode: str = "simulator"
    timeout_seconds: int = 15


@dataclass(frozen=True)
class TelemetrySample:
    """Normalized telemetry payload."""

    active_power_w: float
    voltage_v: float
    current_a: float
    energy_wh: float

    def to_dict(self) -> dict[str, float]:
        return {
            "active_power_w": self.active_power_w,
            "voltage_v": self.voltage_v,
            "current_a": self.current_a,
            "energy_wh": self.energy_wh,
        }


class IEEE20305Client:
    """Fetch and normalize meter telemetry over HTTPS."""

    def __init__(self, config: IEEE20305ClientConfig) -> None:
        self._config = config

    async def fetch_telemetry(self) -> TelemetrySample:
        """Poll the endpoint and normalize telemetry fields.

        Expected payload keys (prototype):
        - active_power_w
        - voltage_v
        - current_a
        - energy_wh
        """
        payload = await self._fetch_json()
        return self._normalize_payload(payload)

    async def _fetch_json(self) -> dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=self._config.timeout_seconds)

        ssl_context = ssl.create_default_context(cafile=self._config.ca_cert)
        ssl_context.load_cert_chain(self._config.client_cert, self._config.client_key)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self._config.endpoint, ssl=ssl_context) as response:
                response.raise_for_status()
                data = await response.json()

        if not isinstance(data, dict):
            raise ValueError("Expected JSON object payload")
        return data

    def _normalize_payload(self, payload: dict[str, Any]) -> TelemetrySample:
        def _as_float(key: str) -> float:
            value = payload.get(key)
            if value is None:
                raise ValueError(f"Missing telemetry key: {key}")
            return float(value)

        return TelemetrySample(
            active_power_w=_as_float("active_power_w"),
            voltage_v=_as_float("voltage_v"),
            current_a=_as_float("current_a"),
            energy_wh=_as_float("energy_wh"),
        )
