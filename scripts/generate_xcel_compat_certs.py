"""Generate Xcel-compatible local test credentials.

This aligns with the common generate_keys.sh pattern used by xcel_itron2mqtt:
- EC P-256 private key
- Self-signed certificate
- CN=MeterReaderHanClient
- certificatePolicies critical, 1.3.6.1.4.1.40732.2.2
- keyUsage critical, digitalSignature
- Long validity (default 7300 days)

Outputs are written to a gitignored .secrets directory by default.
"""

from __future__ import annotations

from argparse import ArgumentParser
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier

DEFAULT_OUT_DIR = Path(".secrets") / "ieee20305" / "xcel-compat"
CERT_FILENAME = ".cert.pem"
KEY_FILENAME = ".key.pem"
POLICY_OID = ObjectIdentifier("1.3.6.1.4.1.40732.2.2")


def _parser() -> ArgumentParser:
    parser = ArgumentParser(description="Generate Xcel-compatible IEEE 2030.5 cert/key")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory (default: .secrets/ieee20305/xcel-compat)",
    )
    parser.add_argument(
        "--cn",
        default="MeterReaderHanClient",
        help="Certificate common name (default: MeterReaderHanClient)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7300,
        help="Certificate validity in days (default: 7300)",
    )
    parser.add_argument(
        "--if-missing",
        action="store_true",
        help="Only generate when cert/key are missing",
    )
    parser.add_argument(
        "--print-lfdi",
        action="store_true",
        help="Print only the 40-char LFDI and exit",
    )
    return parser


def _lfdi_from_cert(cert: x509.Certificate) -> str:
    certificate_der = cert.public_bytes(serialization.Encoding.DER)
    return hashlib.sha256(certificate_der).digest()[:20].hex().upper()


def _read_cert(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


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


def main() -> int:
    args = _parser().parse_args()

    out_dir = args.out_dir.resolve()
    cert_path = out_dir / CERT_FILENAME
    key_path = out_dir / KEY_FILENAME
    metadata_path = out_dir / "metadata.json"

    if args.print_lfdi:
        if not cert_path.exists():
            raise SystemExit(f"Certificate not found at {cert_path}")
        print(_lfdi_from_cert(_read_cert(cert_path)))
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)

    if args.if_missing and cert_path.exists() and key_path.exists():
        cert = _read_cert(cert_path)
        lfdi = _lfdi_from_cert(cert)
        print(f"Existing cert and key found in {out_dir}, keeping them.")
        print(lfdi)
        return 0

    key, cert = _generate_self_signed_cert(common_name=args.cn, days=args.days)
    _write_private_key(key_path, key)
    _write_cert(cert_path, cert)

    # Self-signed cert acts as trust anchor in local test flows.
    metadata = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "pattern": "xcel_itron2mqtt_generate_keys_sh_compatible",
        "cert": str(cert_path),
        "key": str(key_path),
        "ca_cert": str(cert_path),
        "common_name": args.cn,
        "days": args.days,
        "policy_oid": POLICY_OID.dotted_string,
        "lfdi": _lfdi_from_cert(cert),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Generated cert: {cert_path}")
    print(f"Generated key:  {key_path}")
    print(f"LFDI: {metadata['lfdi']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
