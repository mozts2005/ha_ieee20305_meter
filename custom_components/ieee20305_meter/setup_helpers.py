"""Pure helpers for building integration configuration data."""

from __future__ import annotations

from pathlib import Path

from .const import (
    CONF_AGENT_VERSION,
    CONF_CA_CERT,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_ENDPOINT,
    CONF_MODE,
    CONF_METER_HOST,
    CONF_METER_PORT,
    CONF_POLL_INTERVAL,
    CONF_SHOW_LFDI,
    DEFAULT_CA_CERT_PATH,
    DEFAULT_AGENT_VERSION,
    DEFAULT_CLIENT_CERT_PATH,
    DEFAULT_CLIENT_KEY_PATH,
    DEFAULT_METER_PORT,
    DEFAULT_MODE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SHOW_LFDI,
)


def build_base_url(meter_host: str, meter_port: int = DEFAULT_METER_PORT) -> str:
    """Build the canonical base URL for a meter."""
    return f"https://{meter_host}:{meter_port}"


def build_entry_data(
    meter_host: str,
    meter_port: int = DEFAULT_METER_PORT,
    client_cert: str = DEFAULT_CLIENT_CERT_PATH,
    client_key: str = DEFAULT_CLIENT_KEY_PATH,
    ca_cert: str = DEFAULT_CA_CERT_PATH,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    mode: str = DEFAULT_MODE,
    show_lfdi: bool = DEFAULT_SHOW_LFDI,
    agent_version: str = DEFAULT_AGENT_VERSION,
) -> dict[str, str | int | bool]:
    """Build normalized config-entry data from a simplified host/port form."""
    return {
        CONF_METER_HOST: meter_host,
        CONF_METER_PORT: meter_port,
        CONF_ENDPOINT: build_base_url(meter_host, meter_port),
        CONF_CLIENT_CERT: client_cert,
        CONF_CLIENT_KEY: client_key,
        CONF_CA_CERT: ca_cert,
        CONF_POLL_INTERVAL: poll_interval,
        CONF_MODE: mode,
        CONF_SHOW_LFDI: show_lfdi,
        CONF_AGENT_VERSION: agent_version,
    }


def build_migration_entry_data(
    meter_host: str,
    meter_port: int,
    cert_dir: str,
    cert_file: str,
    key_file: str,
    ca_file: str,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    mode: str = DEFAULT_MODE,
    show_lfdi: bool = DEFAULT_SHOW_LFDI,
    agent_version: str = DEFAULT_AGENT_VERSION,
) -> dict[str, str | int | bool]:
    """Build normalized entry data when reusing the old add-on certificate layout."""
    base_dir = Path(cert_dir)
    return build_entry_data(
        meter_host=meter_host,
        meter_port=meter_port,
        client_cert=str(base_dir / cert_file),
        client_key=str(base_dir / key_file),
        ca_cert=str(base_dir / ca_file),
        poll_interval=poll_interval,
        mode=mode,
        show_lfdi=show_lfdi,
        agent_version=agent_version,
    )