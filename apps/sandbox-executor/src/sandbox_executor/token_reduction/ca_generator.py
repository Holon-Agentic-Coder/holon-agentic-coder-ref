"""Root CA generator for the opt-in local token-reduction proxy.

This module owns exactly one job: guarantee that a *valid* self-signed Root CA exists on
the host so the sandbox can trust the locally-owned MITM proxy.

Actual behaviour:

* ``openssl`` is probed with :func:`shutil.which` before anything is written. When it is
  missing, a :class:`RuntimeError` carrying an actionable install hint is raised.
* The certificate is generated with ``openssl req -x509`` under a 60 second timeout.
  ``subprocess.CalledProcessError`` and ``subprocess.TimeoutExpired`` are translated into
  :class:`RuntimeError` including the captured stderr.
* The private key is created with mode ``0o600`` (owner read/write only).
* Every returned artifact is validated with ``openssl x509 -in <path> -noout`` — both
  after fresh generation and when reusing an existing file — so a previously poisoned
  cache is reported instead of silently trusted.

There is deliberately no "fallback certificate" generator: unparseable PEM blobs would be
cached forever by the existence check and break every TLS client inside the sandbox with
an opaque error. Fail loudly instead.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

_OPENSSL_TIMEOUT_SECONDS = 60

_OPENSSL_INSTALL_HINT = (
    "Install OpenSSL and retry: macOS 'brew install openssl', Debian/Ubuntu 'apt-get install openssl'."
)


def _require_openssl() -> str:
    """Return the absolute path of the ``openssl`` binary or raise with an install hint."""
    openssl_path = shutil.which("openssl")
    if openssl_path is None:
        raise RuntimeError(
            f"openssl binary not found on PATH but is required to manage the Holon Root CA. {_OPENSSL_INSTALL_HINT}"
        )
    return openssl_path


def _assert_valid_cert(ca_cert_path: str) -> None:
    """Assert that ``ca_cert_path`` is a parseable X.509 certificate.

    Raises:
        RuntimeError: If ``openssl`` cannot parse the artifact (or times out doing so).
    """
    openssl_path = shutil.which("openssl") or "openssl"
    try:
        result = subprocess.run(
            [openssl_path, "x509", "-in", ca_cert_path, "-noout"],
            capture_output=True,
            text=True,
            timeout=_OPENSSL_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError(f"Could not validate Root CA certificate at {ca_cert_path}: {exc}") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"Root CA certificate at {ca_cert_path} is not a parseable X.509 certificate "
            f"(openssl: {result.stderr.strip() or 'unknown error'}). "
            f"Delete {os.path.dirname(ca_cert_path)} and re-run to regenerate a fresh Root CA. {_OPENSSL_INSTALL_HINT}"
        )


def _harden_key_permissions(ca_key_path: str) -> None:
    """Restrict the CA private key to owner read/write (``0o600``)."""
    os.chmod(ca_key_path, 0o600)


def generate_root_ca(cert_dir: str | None = None) -> tuple[str, str]:
    """Ensure a valid self-signed Root CA certificate and private key exist.

    Args:
        cert_dir: Directory where certs should be stored. Defaults to ``~/.holon/certs``.

    Returns:
        tuple[str, str]: Paths to ``(ca_cert_path, ca_key_path)``. The certificate is
        guaranteed to be parseable by ``openssl x509`` and the key is mode ``0o600``.

    Raises:
        RuntimeError: If ``openssl`` is unavailable, generation fails or times out, or an
            existing cached certificate is not a parseable X.509 artifact.
    """
    openssl_path = _require_openssl()

    if cert_dir is None:
        cert_dir = os.path.expanduser("~/.holon/certs")

    os.makedirs(cert_dir, exist_ok=True)
    ca_cert_path = os.path.join(cert_dir, "holon-root-ca.crt")
    ca_key_path = os.path.join(cert_dir, "holon-root-ca.key")

    if os.path.exists(ca_cert_path) and os.path.exists(ca_key_path):
        logger.info("Reusing existing Root CA certificate at %s", ca_cert_path)
        _assert_valid_cert(ca_cert_path)
        _harden_key_permissions(ca_key_path)
        return ca_cert_path, ca_key_path

    logger.info("Generating self-signed Root CA certificate at %s", cert_dir)

    # Pre-create the key file with 0o600 so the private key is never world-readable,
    # even briefly, regardless of the caller's umask.
    key_fd = os.open(ca_key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.close(key_fd)

    try:
        subprocess.run(
            [
                openssl_path,
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
            capture_output=True,
            text=True,
            timeout=_OPENSSL_TIMEOUT_SECONDS,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"OpenSSL failed to generate the Holon Root CA in {cert_dir} (exit {exc.returncode}): {stderr or exc}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"OpenSSL timed out after {_OPENSSL_TIMEOUT_SECONDS}s generating the Holon Root CA in {cert_dir}."
        ) from exc

    _harden_key_permissions(ca_key_path)
    _assert_valid_cert(ca_cert_path)

    return ca_cert_path, ca_key_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cert, key = generate_root_ca()
    print(f"Generated Root CA:\n  Cert: {cert}\n  Key:  {key}")
