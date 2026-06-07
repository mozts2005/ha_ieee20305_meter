"""Config flow for IEEE 2030.5 meter integration."""

from __future__ import annotations

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
        """Handle user step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ENDPOINT])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="IEEE 2030.5 Meter", data=user_input)

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

        return self.async_show_form(step_id="user", data_schema=schema)
