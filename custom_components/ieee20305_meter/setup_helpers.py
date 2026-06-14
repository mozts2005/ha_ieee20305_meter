"""Pure helpers for building integration configuration data."""

from __future__ import annotations

from pathlib import Path

from .const import (
    CONF_AGENT_VERSION,
    CONF_CA_CERT,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_DISPLAY_NAME,
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


def _sanitize_device_id(meter_host: str) -> str:
    """Create a safe device ID from meter host for use in paths."""
    device_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in meter_host)
    return device_id or "default"


def build_base_url(meter_host: str, meter_port: int = DEFAULT_METER_PORT) -> str:
    """Build the canonical base URL for a meter."""
    return f"https://{meter_host}:{meter_port}"


def build_device_specific_cert_paths(meter_host: str) -> tuple[str, str, str]:
    """Build device-specific certificate paths based on meter host.

    Returns (client_cert_path, client_key_path, ca_cert_path) with device ID embedded.
    """
    device_id = _sanitize_device_id(meter_host)
    client_cert = DEFAULT_CLIENT_CERT_PATH.format(device_id=device_id)
    client_key = DEFAULT_CLIENT_KEY_PATH.format(device_id=device_id)
    ca_cert = DEFAULT_CA_CERT_PATH.format(device_id=device_id)
    return client_cert, client_key, ca_cert


def build_entry_data(
    meter_host: str,
    meter_port: int = DEFAULT_METER_PORT,
    client_cert: str | None = None,
    client_key: str | None = None,
    ca_cert: str | None = None,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    mode: str = DEFAULT_MODE,
    show_lfdi: bool = DEFAULT_SHOW_LFDI,
    agent_version: str = DEFAULT_AGENT_VERSION,
    display_name: str | None = None,
) -> dict[str, str | int | bool]:
    """Build normalized config-entry data from a simplified host/port form.

    Each meter gets device-specific certificate paths by default,
    allowing multiple independent meters with their own certificates.
    """
    # Use device-specific paths by default
    if client_cert is None or client_key is None or ca_cert is None:
        device_cert, device_key, device_ca = build_device_specific_cert_paths(meter_host)
        if client_cert is None:
            client_cert = device_cert
        if client_key is None:
            client_key = device_key
        if ca_cert is None:
            ca_cert = device_ca

    entry_data: dict[str, str | int | bool] = {
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

    if display_name:
        entry_data[CONF_DISPLAY_NAME] = display_name

    return entry_data


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
    display_name: str | None = None,
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
        display_name=display_name,
    )