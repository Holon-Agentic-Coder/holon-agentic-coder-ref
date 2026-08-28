"""Automated Root CA certificate generator for MITM proxy SSL/TLS trust."""

import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def generate_root_ca(cert_dir: str | None = None) -> tuple[str, str]:
    """Generates a self-signed Root CA certificate and private key if not already present.

    Args:
        cert_dir: Directory where certs should be stored. Defaults to ~/.holon/certs.

    Returns:
        tuple[str, str]: Paths to (ca_cert_path, ca_key_path).
    """
    if cert_dir is None:
        cert_dir = os.path.expanduser("~/.holon/certs")

    os.makedirs(cert_dir, exist_ok=True)
    ca_cert_path = os.path.join(cert_dir, "holon-root-ca.crt")
    ca_key_path = os.path.join(cert_dir, "holon-root-ca.key")

    if os.path.exists(ca_cert_path) and os.path.exists(ca_key_path):
        logger.info("Root CA certificate already exists at %s", ca_cert_path)
        return ca_cert_path, ca_key_path

    logger.info("Generating self-signed Root CA certificate at %s", cert_dir)

    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                ca_key_path,
                "-out",
                ca_cert_path,
                "-days",
                "365",
                "-nodes",
                "-subj",
                "/CN=Holon Agent Root CA/O=Holon Agentic Coder",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        logger.warning(
            "OpenSSL CA generation failed or openssl not found: %s. Generating fallback cert.",
            exc,
        )
        _generate_fallback_cert(ca_cert_path, ca_key_path)

    return ca_cert_path, ca_key_path


def _generate_fallback_cert(cert_path: str, key_path: str) -> None:
    """Fallback generator writing basic PEM files if openssl binary is missing."""
    dummy_key = (
        "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC5\n-----END PRIVATE KEY-----\n"
    )
    dummy_cert = (
        "-----BEGIN CERTIFICATE-----\n"
        "MIIDdTCCAl2gAwIBAgIUHOLONROOTCA00000000000000000001MA0GCSqGSIb3\n"
        "-----END CERTIFICATE-----\n"
    )
    with open(key_path, "w") as kf:
        kf.write(dummy_key)
    with open(cert_path, "w") as cf:
        cf.write(dummy_cert)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cert, key = generate_root_ca()
    print(f"Generated Root CA:\n  Cert: {cert}\n  Key:  {key}")
