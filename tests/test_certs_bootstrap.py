from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from custom_components.ieee20305_meter.certs import (
    _ensure_certificates,
    _migrate_legacy_certificate_paths,
    compute_lfdi,
)


def test_ensure_certificates_generates_missing_files(tmp_path: Path) -> None:
    config_dir = str(tmp_path)
    result = _ensure_certificates(
        config_dir,
        {
            "endpoint": "https://meter.example.local/telemetry",
            "client_cert": "ieee20305_meter/certs/client.crt",
            "client_key": "ieee20305_meter/certs/client.key",
            "ca_cert": "ieee20305_meter/certs/ca.crt",
        },
        "meter_example_local",
    )

    client_cert = Path(result["client_cert"])
    client_key = Path(result["client_key"])
    ca_cert = Path(result["ca_cert"])
    ca_key = ca_cert.with_suffix(f"{ca_cert.suffix}.key")

    assert client_cert.is_file()
    assert client_key.is_file()
    assert ca_cert.is_file()
    assert ca_key.is_file()


def test_compute_lfdi_returns_expected_format(tmp_path: Path) -> None:
    config_dir = str(tmp_path)
    result = _ensure_certificates(
        config_dir,
        {
            "endpoint": "https://meter.example.local/telemetry",
            "client_cert": "ieee20305_meter/certs/client.crt",
            "client_key": "ieee20305_meter/certs/client.key",
            "ca_cert": "ieee20305_meter/certs/ca.crt",
        },
        "meter_example_local",
    )

    lfdi = compute_lfdi(result["client_cert"])

    assert len(lfdi) == 40
    assert lfdi == lfdi.upper()
    int(lfdi, 16)


def test_generated_private_keys_use_ec_p256(tmp_path: Path) -> None:
    config_dir = str(tmp_path)
    result = _ensure_certificates(
        config_dir,
        {
            "endpoint": "https://meter.example.local/telemetry",
            "client_cert": "ieee20305_meter/certs/client.crt",
            "client_key": "ieee20305_meter/certs/client.key",
            "ca_cert": "ieee20305_meter/certs/ca.crt",
        },
        "meter_example_local",
    )

    client_key_path = Path(result["client_key"])
    ca_key_path = Path(result["ca_cert"]).with_suffix(".crt.key")

    client_key = serialization.load_pem_private_key(client_key_path.read_bytes(), password=None)
    ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)

    assert isinstance(client_key, ec.EllipticCurvePrivateKey)
    assert isinstance(ca_key, ec.EllipticCurvePrivateKey)
    assert isinstance(client_key.curve, ec.SECP256R1)
    assert isinstance(ca_key.curve, ec.SECP256R1)


def test_migrate_legacy_paths_copies_shared_certs_to_device_dir(tmp_path: Path) -> None:
    config_dir = str(tmp_path)
    legacy_dir = tmp_path / "ieee20305_meter" / "certs"
    legacy_dir.mkdir(parents=True, exist_ok=True)

    (legacy_dir / "client.crt").write_text("legacy-client", encoding="utf-8")
    (legacy_dir / "client.key").write_text("legacy-key", encoding="utf-8")
    (legacy_dir / "ca.crt").write_text("legacy-ca", encoding="utf-8")
    (legacy_dir / "ca.crt.key").write_text("legacy-ca-key", encoding="utf-8")

    migrated = _migrate_legacy_certificate_paths(
        config_dir,
        {
            "meter_host": "meter.local",
            "client_cert": "ieee20305_meter/certs/client.crt",
            "client_key": "ieee20305_meter/certs/client.key",
            "ca_cert": "ieee20305_meter/certs/ca.crt",
        },
        "meter_local",
    )

    client_cert = Path(migrated["client_cert"])
    client_key = Path(migrated["client_key"])
    ca_cert = Path(migrated["ca_cert"])
    ca_key = ca_cert.with_suffix(".crt.key")

    assert client_cert.as_posix().endswith("ieee20305_meter/certs/meter_local/client.crt")
    assert client_key.as_posix().endswith("ieee20305_meter/certs/meter_local/client.key")
    assert ca_cert.as_posix().endswith("ieee20305_meter/certs/meter_local/ca.crt")
    assert ca_key.is_file()

    assert client_cert.read_text(encoding="utf-8") == "legacy-client"
    assert client_key.read_text(encoding="utf-8") == "legacy-key"
    assert ca_cert.read_text(encoding="utf-8") == "legacy-ca"
