"""Single local physical IEEE 2030.5 test runner.

This script bootstraps xcel-compatible cert material when missing and probes
the local meter over mTLS using known-good physical test defaults.
"""

from __future__ import annotations

from argparse import ArgumentParser
from datetime import UTC, datetime, timedelta
import hashlib
import json
from http.client import HTTPSConnection
from pathlib import Path
import ssl
import socket
import sys
from typing import Any
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier


DEFAULT_COMPAT_DIR = Path(".secrets") / "ieee20305" / "xcel-compat"
DEFAULT_METADATA = DEFAULT_COMPAT_DIR / "metadata.json"
CERT_FILENAME = ".cert.pem"
KEY_FILENAME = ".key.pem"
POLICY_OID = ObjectIdentifier("1.3.6.1.4.1.40732.2.2")
DEFAULT_PORT = 8081
DEFAULT_PATH = "/dcap"
DEFAULT_TIMEOUT = 20
DEFAULT_CIPHER = "ECDHE-ECDSA-AES128-CCM8"


def _parser() -> ArgumentParser:
    parser = ArgumentParser(description="Consolidated local IEEE 2030.5 hardware test")
    parser.add_argument("--host", required=True, help="Device IP/host, e.g. 10.0.2.71")
    return parser


def _lfdi_from_cert(cert: x509.Certificate) -> str:
    certificate_der = cert.public_bytes(serialization.Encoding.DER)
    return hashlib.sha256(certificate_der).digest()[:20].hex().upper()


def _read_cert(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


def _write_private_key(path: Path, key: ec.EllipticCurvePrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _write_cert(path: Path, cert: x509.Certificate) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _generate_self_signed_cert(common_name: str, days: int) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(UTC)

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(
            x509.CertificatePolicies([x509.PolicyInformation(policy_identifier=POLICY_OID, policy_qualifiers=None)]),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    return key, cert


def _ensure_cert_material(out_dir: Path) -> Path:
    cert_path = out_dir / CERT_FILENAME
    key_path = out_dir / KEY_FILENAME
    metadata_path = out_dir / "metadata.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    if cert_path.exists() and key_path.exists() and metadata_path.exists():
        print(f"Existing cert and key found in {out_dir}, keeping them.")
        return metadata_path

    key, cert = _generate_self_signed_cert(common_name="MeterReaderHanClient", days=7300)
    _write_private_key(key_path, key)
    _write_cert(cert_path, cert)

    metadata: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "pattern": "xcel_itron2mqtt_generate_keys_sh_compatible",
        "cert": str(cert_path),
        "key": str(key_path),
        "ca_cert": str(cert_path),
        "common_name": "MeterReaderHanClient",
        "days": 7300,
        "policy_oid": POLICY_OID.dotted_string,
        "lfdi": _lfdi_from_cert(cert),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Generated cert: {cert_path}")
    print(f"Generated key:  {key_path}")
    print(f"LFDI: {metadata['lfdi']}")
    return metadata_path


def _resolve_cert_paths(metadata: dict[str, Any]) -> tuple[Path, Path, Path | None]:
    cert = Path(metadata.get("client_cert") or metadata.get("cert") or "")
    key = Path(metadata.get("client_key") or metadata.get("key") or "")
    ca_cert_value = metadata.get("ca_cert") or metadata.get("ca")
    ca_cert = Path(ca_cert_value) if ca_cert_value else None

    if not cert.is_file() or not key.is_file():
        raise FileNotFoundError(f"Missing cert/key paths: cert={cert} key={key}")

    if ca_cert is not None and not ca_cert.is_file():
        raise FileNotFoundError(f"Missing ca_cert path: ca_cert={ca_cert}")

    return cert, key, ca_cert


def _classify_exception(exc: Exception) -> str:
    if isinstance(exc, (ssl.SSLError, ssl.SSLCertVerificationError)):
        return "tls/auth"
    if isinstance(exc, (socket.timeout, TimeoutError, ConnectionRefusedError, ConnectionResetError, OSError)):
        message = str(exc).lower()
        if "ssl" in message or "tls" in message or "certificate" in message:
            return "tls/auth"
        return "network"
    return "unknown"


def _run_probe(host: str, metadata_path: Path) -> int:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    cert, key, ca_cert = _resolve_cert_paths(metadata)

    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))
    context.set_ciphers(DEFAULT_CIPHER)
    if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
        context.options |= ssl.OP_LEGACY_SERVER_CONNECT

    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    print(f"Using CERT={cert}")
    print(f"Using KEY={key}")
    print(f"Using CA={ca_cert}")
    print(f"Using CIPHER={DEFAULT_CIPHER}")
    print("Verify server cert=False")

    url = f"https://{host}:{DEFAULT_PORT}{DEFAULT_PATH}"
    parsed = urlparse(url)

    try:
        connection = HTTPSConnection(
            host=parsed.hostname,
            port=parsed.port,
            context=context,
            timeout=DEFAULT_TIMEOUT,
        )
        connection.request(
            "GET",
            parsed.path,
            headers={"Accept": "*/*", "Connection": "close"},
        )
        response = connection.getresponse()
        body = response.read(4096)
        content_type = response.getheader("Content-Type", "")
        preview = body.decode("utf-8", errors="replace")[:200].replace("\r", " ").replace("\n", " ")
        print(f"PASS {url} status={response.status} content-type={content_type} body200={preview}")
        connection.close()
        return 0
    except Exception as exc:
        print(f"FAIL {url} exc={type(exc).__name__} class={_classify_exception(exc)} detail={exc}")
        return 1


def main() -> int:
    args = _parser().parse_args()

    metadata_path = _ensure_cert_material(DEFAULT_COMPAT_DIR)
    return _run_probe(args.host, metadata_path)


if __name__ == "__main__":
    raise SystemExit(main())
