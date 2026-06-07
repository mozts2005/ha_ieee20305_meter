"""Config flow for IEEE 2030.5 meter integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CA_CERT,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_ENDPOINT,
    CONF_MODE,
    CONF_POLL_INTERVAL,
    CONF_SHOW_LFDI,
    DEFAULT_CA_CERT_PATH,
    DEFAULT_CLIENT_CERT_PATH,
    DEFAULT_CLIENT_KEY_PATH,
    DEFAULT_MODE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SHOW_LFDI,
    DOMAIN,
    MODES,
)


class IEEE20305ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle IEEE 2030.5 config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show setup mode selection."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["manual", "migrate_from_addon"],
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle manual configuration step."""
        if user_input is not None:
            return await self._create_entry_from_input(user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_ENDPOINT): str,
                vol.Optional(CONF_CLIENT_CERT, default=DEFAULT_CLIENT_CERT_PATH): str,
                vol.Optional(CONF_CLIENT_KEY, default=DEFAULT_CLIENT_KEY_PATH): str,
                vol.Optional(CONF_CA_CERT, default=DEFAULT_CA_CERT_PATH): str,
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=3600)
                ),
                vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(MODES),
                vol.Optional(CONF_SHOW_LFDI, default=DEFAULT_SHOW_LFDI): bool,
            }
        )

        return self.async_show_form(step_id="manual", data_schema=schema)

    async def async_step_migrate_from_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle migration-oriented setup for MQTT add-on users."""
        conf_meter_ip = "meter_ip"
        conf_meter_port = "meter_port"
        conf_cert_dir = "cert_dir"
        conf_cert_file = "cert_file"
        conf_key_file = "key_file"
        conf_ca_file = "ca_file"

        default_meter_port = 8081
        default_cert_dir = f"{DOMAIN}/certs"
        default_cert_file = "client.crt"
        default_key_file = "client.key"
        default_ca_file = "ca.crt"

        if user_input is not None:
            cert_dir = Path(user_input[conf_cert_dir])
            mapped_input = {
                CONF_ENDPOINT: f"https://{user_input[conf_meter_ip]}:{user_input[conf_meter_port]}/telemetry",
                CONF_CLIENT_CERT: str(cert_dir / user_input[conf_cert_file]),
                CONF_CLIENT_KEY: str(cert_dir / user_input[conf_key_file]),
                CONF_CA_CERT: str(cert_dir / user_input[conf_ca_file]),
                CONF_POLL_INTERVAL: user_input[CONF_POLL_INTERVAL],
                CONF_MODE: user_input[CONF_MODE],
                CONF_SHOW_LFDI: user_input[CONF_SHOW_LFDI],
            }
            return await self._create_entry_from_input(mapped_input)

        schema = vol.Schema(
            {
                vol.Required(conf_meter_ip): str,
                vol.Optional(conf_meter_port, default=default_meter_port): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Optional(conf_cert_dir, default=default_cert_dir): str,
                vol.Optional(conf_cert_file, default=default_cert_file): str,
                vol.Optional(conf_key_file, default=default_key_file): str,
                vol.Optional(conf_ca_file, default=default_ca_file): str,
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=3600)
                ),
                vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(MODES),
                vol.Optional(CONF_SHOW_LFDI, default=DEFAULT_SHOW_LFDI): bool,
            }
        )

        return self.async_show_form(step_id="migrate_from_addon", data_schema=schema)

    async def _create_entry_from_input(self, user_input: dict[str, Any]) -> FlowResult:
        """Create entry after enforcing uniqueness by endpoint."""
        await self.async_set_unique_id(user_input[CONF_ENDPOINT])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="IEEE 2030.5 Meter", data=user_input)
