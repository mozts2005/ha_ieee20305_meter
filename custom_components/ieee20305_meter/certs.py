"""Certificate bootstrap utilities for first-run setup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import shutil
import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import (
    CONF_CA_CERT,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    DOMAIN,
    DEFAULT_CA_CERT_PATH,
    DEFAULT_CLIENT_CERT_PATH,
    DEFAULT_CLIENT_KEY_PATH,
)

_LOGGER = logging.getLogger(__name__)

LEGACY_CLIENT_CERT_PATH = f"{DOMAIN}/certs/client.crt"
LEGACY_CLIENT_KEY_PATH = f"{DOMAIN}/certs/client.key"
LEGACY_CA_CERT_PATH = f"{DOMAIN}/certs/ca.crt"


def _get_device_id(data: dict[str, Any]) -> str:
    """Extract device identifier from config data.

    Returns a sanitized device ID based on meter host for uniqueness.
    """
    meter_host = data.get("meter_host", "unknown")
    # Sanitize the host to create a valid directory name
    device_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in meter_host)
    return device_id or "default"


async def async_ensure_certificates(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Ensure certificate files exist and return normalized config paths."""
    device_id = _get_device_id(data)
    return await hass.async_add_executor_job(
        _ensure_certificates, hass.config.config_dir, data, device_id
    )


async def async_migrate_legacy_certificate_paths(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Migrate legacy centralized certificate paths to per-device paths.

    Existing installs used a shared certificate layout:
    - ieee20305_meter/certs/client.crt
    - ieee20305_meter/certs/client.key
    - ieee20305_meter/certs/ca.crt

    This migration copies legacy certificates to the per-device layout and updates
    entry configuration paths. Source files are not deleted.
    """
    device_id = _get_device_id(data)
    return await hass.async_add_executor_job(
        _migrate_legacy_certificate_paths,
        hass.config.config_dir,
        data,
        device_id,
    )


async def async_has_deprecated_certificate_paths(
    hass: HomeAssistant, data: dict[str, Any]
) -> bool:
    """Return True when config still uses deprecated shared certificate layout."""
    return await hass.async_add_executor_job(
        _has_deprecated_certificate_paths,
        hass.config.config_dir,
        data,
    )


def _ensure_certificates(config_dir: str, data: dict[str, Any], device_id: str) -> dict[str, Any]:
    """Ensure device-specific certificates exist."""
    endpoint = str(data.get("endpoint", ""))

    # Resolve paths with device-specific defaults
    client_cert_default = DEFAULT_CLIENT_CERT_PATH.format(device_id=device_id)
    client_key_default = DEFAULT_CLIENT_KEY_PATH.format(device_id=device_id)
    ca_cert_default = DEFAULT_CA_CERT_PATH.format(device_id=device_id)

    client_cert_path = _resolve_path(config_dir, data.get(CONF_CLIENT_CERT) or client_cert_default)
    client_key_path = _resolve_path(config_dir, data.get(CONF_CLIENT_KEY) or client_key_default)
    ca_cert_path = _resolve_path(config_dir, data.get(CONF_CA_CERT) or ca_cert_default)
    ca_key_path = ca_cert_path.with_suffix(f"{ca_cert_path.suffix}.key")

    new_data = dict(data)
    new_data[CONF_CLIENT_CERT] = str(client_cert_path)
    new_data[CONF_CLIENT_KEY] = str(client_key_path)
    new_data[CONF_CA_CERT] = str(ca_cert_path)

    if client_cert_path.exists() and client_key_path.exists() and ca_cert_path.exists():
        _LOGGER.debug(
            "Device %s: Using existing certificates at %s",
            device_id,
            client_cert_path.parent,
        )
        return new_data

    client_cert_path.parent.mkdir(parents=True, exist_ok=True)
    client_key_path.parent.mkdir(parents=True, exist_ok=True)
    ca_cert_path.parent.mkdir(parents=True, exist_ok=True)

    if not ca_cert_path.exists() or not ca_key_path.exists():
        _LOGGER.info(
            "Device %s: Generating local CA certificate for IEEE 2030.5 integration",
            device_id,
        )
        ca_key, ca_cert = _generate_ca_certificate(device_id=device_id)
        _write_private_key(ca_key_path, ca_key)
        _write_certificate(ca_cert_path, ca_cert)
    else:
        ca_key = _load_private_key(ca_key_path)
        ca_cert = _load_certificate(ca_cert_path)

    if not client_cert_path.exists() or not client_key_path.exists():
        _LOGGER.info(
            "Device %s: Generating client certificate and key for IEEE 2030.5 integration",
            device_id,
        )
        client_key, client_cert = _generate_client_certificate(
            ca_key=ca_key,
            ca_cert=ca_cert,
            endpoint=endpoint,
            device_id=device_id,
        )
        _write_private_key(client_key_path, client_key)
        _write_certificate(client_cert_path, client_cert)

    return new_data


def _migrate_legacy_certificate_paths(
    config_dir: str,
    data: dict[str, Any],
    device_id: str,
) -> dict[str, Any]:
    """Copy legacy centralized certificates into per-device paths."""
    current_client = _resolve_path(
        config_dir,
        str(data.get(CONF_CLIENT_CERT) or LEGACY_CLIENT_CERT_PATH),
    )
    current_key = _resolve_path(
        config_dir,
        str(data.get(CONF_CLIENT_KEY) or LEGACY_CLIENT_KEY_PATH),
    )
    current_ca = _resolve_path(
        config_dir,
        str(data.get(CONF_CA_CERT) or LEGACY_CA_CERT_PATH),
    )

    legacy_client = _resolve_path(config_dir, LEGACY_CLIENT_CERT_PATH)
    legacy_key = _resolve_path(config_dir, LEGACY_CLIENT_KEY_PATH)
    legacy_ca = _resolve_path(config_dir, LEGACY_CA_CERT_PATH)

    # Migrate either the exact historical defaults or any deprecated shared layout
    # under ieee20305_meter/certs/* where all entries share one cert directory.
    is_exact_legacy_defaults = (
        current_client == legacy_client
        and current_key == legacy_key
        and current_ca == legacy_ca
    )
    is_deprecated_shared_layout = (
        _is_legacy_shared_path(current_client)
        and _is_legacy_shared_path(current_key)
        and _is_legacy_shared_path(current_ca)
    )

    if not (is_exact_legacy_defaults or is_deprecated_shared_layout):
        return data

    target_client = _resolve_path(
        config_dir,
        DEFAULT_CLIENT_CERT_PATH.format(device_id=device_id),
    )
    target_key = _resolve_path(
        config_dir,
        DEFAULT_CLIENT_KEY_PATH.format(device_id=device_id),
    )
    target_ca = _resolve_path(
        config_dir,
        DEFAULT_CA_CERT_PATH.format(device_id=device_id),
    )

    target_client.parent.mkdir(parents=True, exist_ok=True)
    target_key.parent.mkdir(parents=True, exist_ok=True)
    target_ca.parent.mkdir(parents=True, exist_ok=True)

    try:
        if current_client.exists() and not target_client.exists():
            shutil.copy2(current_client, target_client)
        if current_key.exists() and not target_key.exists():
            shutil.copy2(current_key, target_key)
        if current_ca.exists() and not target_ca.exists():
            shutil.copy2(current_ca, target_ca)

        legacy_ca_key = current_ca.with_suffix(f"{current_ca.suffix}.key")
        target_ca_key = target_ca.with_suffix(f"{target_ca.suffix}.key")
        if legacy_ca_key.exists() and not target_ca_key.exists():
            shutil.copy2(legacy_ca_key, target_ca_key)
    except OSError as err:
        _LOGGER.warning(
            "Device %s: unable to migrate deprecated certificate layout: %s",
            device_id,
            err,
        )
        return data

    _LOGGER.info(
        "Device %s: migrated legacy shared certificate paths to per-device directory %s",
        device_id,
        target_client.parent,
    )

    new_data = dict(data)
    new_data[CONF_CLIENT_CERT] = str(target_client)
    new_data[CONF_CLIENT_KEY] = str(target_key)
    new_data[CONF_CA_CERT] = str(target_ca)
    return new_data


def _has_deprecated_certificate_paths(config_dir: str, data: dict[str, Any]) -> bool:
    """Check whether any configured cert path still uses deprecated shared layout."""
    client = _resolve_path(
        config_dir,
        str(data.get(CONF_CLIENT_CERT) or LEGACY_CLIENT_CERT_PATH),
    )
    key = _resolve_path(
        config_dir,
        str(data.get(CONF_CLIENT_KEY) or LEGACY_CLIENT_KEY_PATH),
    )
    ca = _resolve_path(
        config_dir,
        str(data.get(CONF_CA_CERT) or LEGACY_CA_CERT_PATH),
    )
    return _is_legacy_shared_path(client) or _is_legacy_shared_path(key) or _is_legacy_shared_path(ca)


def _is_legacy_shared_path(path: Path) -> bool:
    """Return True for paths under .../ieee20305_meter/certs/<file>."""
    parts = path.parts
    return len(parts) >= 3 and parts[-3] == DOMAIN and parts[-2] == "certs"


def _resolve_path(config_dir: str, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    return Path(config_dir) / path


def _generate_ca_certificate(device_id: str) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "IEEE20305 Meter Integration"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"IEEE20305 Local CA - {device_id}"),
        ]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                key_cert_sign=True,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    return key, cert


def _generate_client_certificate(
    ca_key: ec.EllipticCurvePrivateKey,
    ca_cert: x509.Certificate,
    endpoint: str,
    device_id: str,
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    endpoint_host = _endpoint_host(endpoint)

    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "IEEE20305 Meter Integration"),
            x509.NameAttribute(NameOID.COMMON_NAME, endpoint_host),
        ]
    )

    now = datetime.now(UTC)
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(endpoint_host)]), critical=False)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                key_cert_sign=False,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    )

    cert = cert_builder.sign(private_key=ca_key, algorithm=hashes.SHA256())
    return key, cert


def _endpoint_host(endpoint: str) -> str:
    try:
        parsed = urlparse(endpoint)
    except ValueError:
        return "ieee20305-client"

    if parsed.hostname:
        return parsed.hostname
    return "ieee20305-client"


def _write_private_key(path: Path, key: ec.EllipticCurvePrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def _write_certificate(path: Path, cert: x509.Certificate) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _load_private_key(path: Path) -> ec.EllipticCurvePrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise TypeError("Expected EC private key for CA")
    return key


def _load_certificate(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


def compute_lfdi(certificate_path: str) -> str:
    """Compute IEEE 2030.5 LFDI from a PEM certificate path.

    LFDI is the left-most 160 bits of SHA-256 over DER certificate bytes.
    """
    certificate = x509.load_pem_x509_certificate(Path(certificate_path).read_bytes())
    certificate_der = certificate.public_bytes(encoding=serialization.Encoding.DER)
    return hashlib.sha256(certificate_der).digest()[:20].hex().upper()
