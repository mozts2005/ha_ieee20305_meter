"""Certificate bootstrap utilities for first-run setup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import (
    CONF_CA_CERT,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    DEFAULT_CA_CERT_PATH,
    DEFAULT_CLIENT_CERT_PATH,
    DEFAULT_CLIENT_KEY_PATH,
)

_LOGGER = logging.getLogger(__name__)


async def async_ensure_certificates(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Ensure certificate files exist and return normalized config paths."""
    return await hass.async_add_executor_job(_ensure_certificates, hass.config.config_dir, data)


def _ensure_certificates(config_dir: str, data: dict[str, Any]) -> dict[str, Any]:
    endpoint = str(data.get("endpoint", ""))

    client_cert_path = _resolve_path(config_dir, data.get(CONF_CLIENT_CERT) or DEFAULT_CLIENT_CERT_PATH)
    client_key_path = _resolve_path(config_dir, data.get(CONF_CLIENT_KEY) or DEFAULT_CLIENT_KEY_PATH)
    ca_cert_path = _resolve_path(config_dir, data.get(CONF_CA_CERT) or DEFAULT_CA_CERT_PATH)
    ca_key_path = ca_cert_path.with_suffix(f"{ca_cert_path.suffix}.key")

    new_data = dict(data)
    new_data[CONF_CLIENT_CERT] = str(client_cert_path)
    new_data[CONF_CLIENT_KEY] = str(client_key_path)
    new_data[CONF_CA_CERT] = str(ca_cert_path)

    if client_cert_path.exists() and client_key_path.exists() and ca_cert_path.exists():
        return new_data

    client_cert_path.parent.mkdir(parents=True, exist_ok=True)
    client_key_path.parent.mkdir(parents=True, exist_ok=True)
    ca_cert_path.parent.mkdir(parents=True, exist_ok=True)

    if not ca_cert_path.exists() or not ca_key_path.exists():
        _LOGGER.info("Generating local CA certificate for IEEE 2030.5 integration")
        ca_key, ca_cert = _generate_ca_certificate()
        _write_private_key(ca_key_path, ca_key)
        _write_certificate(ca_cert_path, ca_cert)
    else:
        ca_key = _load_private_key(ca_key_path)
        ca_cert = _load_certificate(ca_cert_path)

    if not client_cert_path.exists() or not client_key_path.exists():
        _LOGGER.info("Generating client certificate and key for IEEE 2030.5 integration")
        client_key, client_cert = _generate_client_certificate(
            ca_key=ca_key,
            ca_cert=ca_cert,
            endpoint=endpoint,
        )
        _write_private_key(client_key_path, client_key)
        _write_certificate(client_cert_path, client_cert)

    return new_data


def _resolve_path(config_dir: str, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path
    return Path(config_dir) / path


def _generate_ca_certificate() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "IEEE20305 Meter Integration"),
            x509.NameAttribute(NameOID.COMMON_NAME, "IEEE20305 Local CA"),
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
                digital_signature=False,
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
    ca_key: rsa.RSAPrivateKey,
    ca_cert: x509.Certificate,
    endpoint: str,
) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
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
                key_encipherment=True,
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


def _write_private_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def _write_certificate(path: Path, cert: x509.Certificate) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _load_private_key(path: Path) -> rsa.RSAPrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise TypeError("Expected RSA private key for CA")
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
