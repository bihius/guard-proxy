"""Certbot service for provisioning Let's Encrypt certificates."""

import logging
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Certbot's working directories. They live inside the backend container rather
# than on a volume: every renewal re-issues from scratch anyway, so the only
# thing a persisted account would save is one ACME account registration.
_CONFIG_DIR = "/tmp/certbot/config"
_WORK_DIR = "/tmp/certbot/work"
_LOGS_DIR = "/tmp/certbot/logs"


class CertbotError(Exception):
    """Raised when certbot fails to provision a certificate."""


def build_certbot_command(
    *, domain: str, email: str, port: int, server_url: str | None
) -> list[str]:
    """Build the `certbot certonly` invocation used for issuance and renewal.

    `server_url` is the ACME directory. `None` leaves certbot on its own
    default (Let's Encrypt production); anything else is passed as `--server`,
    which is what makes staging directories and local ACME servers (Pebble)
    usable. A private CA for that server is trusted through certbot's own
    REQUESTS_CA_BUNDLE environment variable, which the subprocess inherits.
    """
    command = [
        "certbot",
        "certonly",
        "--standalone",
        "--http-01-port",
        str(port),
        "-d",
        domain,
        "--non-interactive",
        "--agree-tos",
        "-m",
        email,
        "--config-dir",
        _CONFIG_DIR,
        "--work-dir",
        _WORK_DIR,
        "--logs-dir",
        _LOGS_DIR,
    ]
    if server_url:
        command += ["--server", server_url]
    return command


class CertbotService:
    """Orchestrates certbot to obtain and renew Let's Encrypt certificates.

    This service invokes the certbot binary (which must be installed in the
    environment) and uses the standalone plugin. The standalone plugin listens
    on port 8888, which HAProxy is configured to route
    `.well-known/acme-challenge/` requests to.
    """

    def __init__(self, port: int = 8888):
        self.port = port

    def provision_cert(self, domain: str, email: str) -> tuple[str, str]:
        """
        Provisions a certificate for the given domain using certbot.

        Returns:
            (cert_pem, key_pem): The contents of the fullchain.pem and privkey.pem.
        """
        logger.info(
            f"Provisioning Let's Encrypt certificate for {domain} (email: {email})"
        )

        cmd = build_certbot_command(
            domain=domain,
            email=email,
            port=self.port,
            server_url=settings.acme_server_url,
        )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logger.error(
                    f"Certbot failed for {domain}. "
                    f"stdout: {result.stdout} stderr: {result.stderr}"
                )
                raise CertbotError(f"Certbot failed: {result.stderr or result.stdout}")

            # Read the generated certificates
            live_dir = Path(_CONFIG_DIR) / "live" / domain
            cert_path = live_dir / "fullchain.pem"
            key_path = live_dir / "privkey.pem"

            if not cert_path.exists() or not key_path.exists():
                raise CertbotError(
                    "Certbot succeeded but certificate files were not found."
                )

            with open(cert_path) as f:
                cert_pem = f.read()

            with open(key_path) as f:
                key_pem = f.read()

            return cert_pem, key_pem

        except FileNotFoundError:
            logger.error("certbot binary not found. Is it installed?")
            raise CertbotError("certbot binary not found.")

