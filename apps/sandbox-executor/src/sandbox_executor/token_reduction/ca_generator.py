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
        logger.error(
            "OpenSSL Root CA generation failed. "
            "Please ensure the 'openssl' command line utility is installed and functional."
        )
        raise RuntimeError(
            "OpenSSL is required to generate Root CA certificates for the token reduction proxy, "
            "but it is not installed or failed to execute."
        ) from exc

    return ca_cert_path, ca_key_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cert, key = generate_root_ca()
    print(f"Generated Root CA:\n  Cert: {cert}\n  Key:  {key}")
