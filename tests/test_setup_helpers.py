from pathlib import Path

from custom_components.ieee20305_meter.setup_helpers import (
    build_base_url,
    build_entry_data,
    build_migration_entry_data,
)


def test_build_entry_data_uses_simple_host_and_port() -> None:
    entry = build_entry_data("192.168.1.25", meter_port=8081, poll_interval=45)

    assert entry["meter_host"] == "192.168.1.25"
    assert entry["meter_port"] == 8081
    assert entry["endpoint"] == "https://192.168.1.25:8081"
    assert entry["poll_interval"] == 45
    assert entry["agent_version"] == "auto"


def test_build_migration_entry_data_reuses_old_cert_layout() -> None:
    entry = build_migration_entry_data(
        meter_host="meter.local",
        meter_port=8081,
        cert_dir="legacy/certs",
        cert_file="cert.pem",
        key_file="key.pem",
        ca_file="ca.pem",
    )

    assert build_base_url("meter.local", 8081) == entry["endpoint"]
    assert Path(entry["client_cert"]).as_posix().endswith("legacy/certs/cert.pem")
    assert Path(entry["client_key"]).as_posix().endswith("legacy/certs/key.pem")
    assert Path(entry["ca_cert"]).as_posix().endswith("legacy/certs/ca.pem")