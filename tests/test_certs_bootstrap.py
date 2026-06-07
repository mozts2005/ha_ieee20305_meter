from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from custom_components.ieee20305_meter.certs import _ensure_certificates, compute_lfdi


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
    )

    client_key_path = Path(result["client_key"])
    ca_key_path = Path(result["ca_cert"]).with_suffix(".crt.key")

    client_key = serialization.load_pem_private_key(client_key_path.read_bytes(), password=None)
    ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)

    assert isinstance(client_key, ec.EllipticCurvePrivateKey)
    assert isinstance(ca_key, ec.EllipticCurvePrivateKey)
    assert isinstance(client_key.curve, ec.SECP256R1)
    assert isinstance(ca_key.curve, ec.SECP256R1)
