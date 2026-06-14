"""Config flow for IEEE 2030.5 meter integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AGENT_VERSIONS,
    CONF_AGENT_VERSION,
    CONF_CA_CERT,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_DISPLAY_NAME,
    CONF_ENDPOINT,
    CONF_METER_HOST,
    CONF_METER_PORT,
    CONF_MODE,
    CONF_POLL_INTERVAL,
    CONF_SHOW_LFDI,
    DEFAULT_METER_PORT,
    DEFAULT_AGENT_VERSION,
    DEFAULT_MODE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SHOW_LFDI,
    DOMAIN,
    MODES,
)
from .setup_helpers import build_base_url, build_entry_data, build_migration_entry_data

_LOGGER = logging.getLogger(__name__)


class IEEE20305ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle IEEE 2030.5 config flow."""

    VERSION = 1
    _pending_user_input: dict[str, Any] | None = None

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> IEEE20305OptionsFlow:
        """Return the options flow for this handler."""
        return IEEE20305OptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the simplified primary setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            display_name = str(user_input.get(CONF_DISPLAY_NAME, "")).strip()
            if display_name:
                user_input[CONF_DISPLAY_NAME] = display_name
            else:
                user_input.pop(CONF_DISPLAY_NAME, None)

            # Validate meter host
            if not user_input.get(CONF_METER_HOST):
                errors[CONF_METER_HOST] = "invalid_host"

            if not errors:
                migrate_existing = user_input.pop("migrate_existing_addon_paths", False)
                if migrate_existing:
                    self._pending_user_input = user_input
                    return await self.async_step_migrate_from_addon()
                entry_data = build_entry_data(**user_input)
                return await self._create_entry_from_input(entry_data)

        schema = vol.Schema(
            {
                vol.Required(CONF_METER_HOST): str,
                vol.Optional(CONF_METER_PORT, default=DEFAULT_METER_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=3600)
                ),
                vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(MODES),
                vol.Optional(CONF_AGENT_VERSION, default=DEFAULT_AGENT_VERSION): vol.In(
                    AGENT_VERSIONS
                ),
                vol.Optional(CONF_DISPLAY_NAME, default=""): str,
                vol.Optional(CONF_SHOW_LFDI, default=DEFAULT_SHOW_LFDI): bool,
                vol.Optional("migrate_existing_addon_paths", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_migrate_from_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reuse certificate layout from the old MQTT add-on."""
        conf_cert_dir = "cert_dir"
        conf_cert_file = "cert_file"
        conf_key_file = "key_file"
        conf_ca_file = "ca_file"

        default_cert_dir = f"{DOMAIN}/certs"
        default_cert_file = "client.crt"
        default_key_file = "client.key"
        default_ca_file = "ca.crt"

        if user_input is not None:
            if self._pending_user_input is None:
                return await self.async_step_user()
            mapped_input = build_migration_entry_data(
                meter_host=self._pending_user_input[CONF_METER_HOST],
                meter_port=self._pending_user_input[CONF_METER_PORT],
                cert_dir=user_input[conf_cert_dir],
                cert_file=user_input[conf_cert_file],
                key_file=user_input[conf_key_file],
                ca_file=user_input[conf_ca_file],
                poll_interval=self._pending_user_input[CONF_POLL_INTERVAL],
                mode=self._pending_user_input[CONF_MODE],
                show_lfdi=self._pending_user_input[CONF_SHOW_LFDI],
                agent_version=self._pending_user_input[CONF_AGENT_VERSION],
                display_name=self._pending_user_input.get(CONF_DISPLAY_NAME),
            )
            self._pending_user_input = None
            return await self._create_entry_from_input(mapped_input)

        schema = vol.Schema(
            {
                vol.Optional(conf_cert_dir, default=default_cert_dir): str,
                vol.Optional(conf_cert_file, default=default_cert_file): str,
                vol.Optional(conf_key_file, default=default_key_file): str,
                vol.Optional(conf_ca_file, default=default_ca_file): str,
            }
        )

        return self.async_show_form(step_id="migrate_from_addon", data_schema=schema)

    async def _create_entry_from_input(self, user_input: dict[str, Any]) -> FlowResult:
        """Create entry after enforcing uniqueness by meter base URL."""
        unique_id = build_base_url(
            str(user_input[CONF_METER_HOST]),
            int(user_input[CONF_METER_PORT]),
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        meter_host = user_input.get(CONF_METER_HOST, "Meter")
        display_name = str(user_input.get(CONF_DISPLAY_NAME, "")).strip()
        entry_title = display_name or f"IEEE 2030.5 Meter - {meter_host}"

        return self.async_create_entry(title=entry_title, data=user_input)


class IEEE20305OptionsFlow(config_entries.OptionsFlow):
    """Handle options for IEEE 2030.5 meter integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage integration options."""
        base = dict(self._config_entry.data)
        base.update(self._config_entry.options)

        if user_input is not None:
            display_name = str(user_input.get(CONF_DISPLAY_NAME, "")).strip()
            if display_name:
                user_input[CONF_DISPLAY_NAME] = display_name
            else:
                user_input.pop(CONF_DISPLAY_NAME, None)

            entry_data = build_entry_data(
                meter_host=user_input[CONF_METER_HOST],
                meter_port=user_input[CONF_METER_PORT],
                client_cert=str(base[CONF_CLIENT_CERT]),
                client_key=str(base[CONF_CLIENT_KEY]),
                ca_cert=str(base[CONF_CA_CERT]),
                poll_interval=user_input[CONF_POLL_INTERVAL],
                mode=user_input[CONF_MODE],
                show_lfdi=user_input[CONF_SHOW_LFDI],
                agent_version=user_input[CONF_AGENT_VERSION],
                display_name=user_input.get(CONF_DISPLAY_NAME),
            )
            entry_data[CONF_ENDPOINT] = build_base_url(
                str(user_input[CONF_METER_HOST]), int(user_input[CONF_METER_PORT])
            )

            meter_host = user_input[CONF_METER_HOST]
            entry_title = display_name or f"IEEE 2030.5 Meter - {meter_host}"
            hass = getattr(self, "hass", None)
            if hass is not None:
                hass.config_entries.async_update_entry(self._config_entry, title=entry_title)

            return self.async_create_entry(title="", data=entry_data)

        schema = vol.Schema(
            {
                vol.Required(CONF_METER_HOST, default=base[CONF_METER_HOST]): str,
                vol.Optional(CONF_METER_PORT, default=base[CONF_METER_PORT]): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_POLL_INTERVAL, default=base[CONF_POLL_INTERVAL]): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=3600)
                ),
                vol.Optional(CONF_MODE, default=base[CONF_MODE]): vol.In(MODES),
                vol.Optional(CONF_AGENT_VERSION, default=base[CONF_AGENT_VERSION]): vol.In(
                    AGENT_VERSIONS
                ),
                vol.Optional(
                    CONF_DISPLAY_NAME,
                    default=str(base.get(CONF_DISPLAY_NAME, self._config_entry.title or "")),
                ): str,
                vol.Optional(CONF_SHOW_LFDI, default=base[CONF_SHOW_LFDI]): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
