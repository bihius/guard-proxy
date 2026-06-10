"""Certbot service for provisioning Let's Encrypt certificates."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class CertbotError(Exception):
    """Raised when certbot fails to provision a certificate."""


class CertbotService:
    """Orchestrates certbot to obtain and renew Let's Encrypt certificates.
    
    This service invokes the certbot binary (which must be installed in the environment)
    and uses the standalone plugin. The standalone plugin listens on port 8888, which
    HAProxy is configured to route `.well-known/acme-challenge/` requests to.
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
        
        # certbot certonly --standalone --http-01-port 8888 -d example.com
        # --non-interactive --agree-tos -m admin@example.com
        cmd = [
            "certbot",
            "certonly",
            "--standalone",
            "--http-01-port",
            str(self.port),
            "-d",
            domain,
            "--non-interactive",
            "--agree-tos",
            "-m",
            email,
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logger.error(
                    f"Certbot failed for {domain}. "
                    f"stdout: {result.stdout} stderr: {result.stderr}"
                )
                raise CertbotError(f"Certbot failed: {result.stderr or result.stdout}")
                
            # Read the generated certificates
            live_dir = Path("/etc/letsencrypt/live") / domain
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
