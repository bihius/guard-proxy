"""VHost service for vhost domain logic."""

import logging
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.policy import Policy
from app.models.vhost import VHost
from app.services.certbot_service import CertbotError, CertbotService

logger = logging.getLogger(__name__)

NON_NULLABLE_PATCH_FIELDS = {
    "domain",
    "backend_url",
    "ssl_enabled",
    "ssl_provider",
    "is_active",
}


class VHostError(Exception):
    """Base class for vhost domain errors."""


class VHostNotFoundError(VHostError):
    """Raised when a vhost does not exist."""


class VHostDomainAlreadyExistsError(VHostError):
    """Raised when a vhost domain conflicts with an existing row."""


class VHostFieldCannotBeNullError(VHostError):
    """Raised when PATCH sets a non-nullable field to null."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field '{field_name}' cannot be null")


class VHostPolicyNotFoundError(VHostError):
    """Raised when a referenced policy does not exist."""


class VHostService:
    """Encapsulates vhost CRUD business rules."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_vhost(
        self,
        *,
        domain: str,
        backend_url: str,
        description: str | None,
        ssl_enabled: bool,
        ssl_provider: str = "none",
        ssl_cert: str | None = None,
        ssl_key: str | None = None,
        is_active: bool,
        policy_id: int | None,
        created_by: int | None,
        user_email: str | None = None,
    ) -> VHost:
        """Create and persist a new vhost."""
        self._ensure_policy_exists(policy_id)

        ssl_expires_at = None
        if ssl_provider == "upload" and ssl_cert:
            ssl_expires_at = self._parse_cert_expiration(ssl_cert)
        elif ssl_provider == "letsencrypt":
            email = user_email or f"admin@{domain}"
            certbot = CertbotService()
            try:
                ssl_cert, ssl_key = certbot.provision_cert(domain, email)
                ssl_expires_at = self._parse_cert_expiration(ssl_cert)
            except CertbotError as e:
                logger.error(f"Failed to provision cert for {domain}: {e}")
                # We can either fail the creation or save it without certs.
                # Let's fail it so the user knows.
                raise ValueError(f"Let's Encrypt provisioning failed: {e}")

        vhost = VHost(
            domain=domain,
            backend_url=backend_url,
            description=description,
            ssl_enabled=ssl_enabled,
            ssl_provider=ssl_provider,
            ssl_cert=ssl_cert,
            ssl_key=ssl_key,
            ssl_expires_at=ssl_expires_at,
            is_active=is_active,
            policy_id=policy_id,
            created_by=created_by,
        )
        self.db.add(vhost)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            if self._is_vhost_domain_unique_violation(error):
                raise VHostDomainAlreadyExistsError from error
            raise

        self.db.refresh(vhost)
        return vhost

    def list_vhosts(self) -> list[VHost]:
        """Return all vhosts sorted by ID."""
        return self.db.query(VHost).order_by(VHost.id.asc()).all()

    def get_vhost(self, vhost_id: int) -> VHost:
        """Return one vhost with related policy loaded."""
        vhost = (
            self.db.query(VHost)
            .options(selectinload(VHost.policy))
            .filter(VHost.id == vhost_id)
            .first()
        )
        if vhost is None:
            raise VHostNotFoundError
        return vhost

    def update_vhost(
        self,
        vhost_id: int,
        patch_data: dict[str, object],
        user_email: str | None = None,
    ) -> VHost:
        """Update selected vhost fields."""
        vhost = self._get_vhost_or_raise(vhost_id)
        self._validate_patch_data(patch_data)

        if "policy_id" in patch_data:
            self._ensure_policy_exists(patch_data["policy_id"])

        ssl_provider = patch_data.get("ssl_provider", vhost.ssl_provider)
        
        # If cert changes or provider changes to letsencrypt, handle it
        if "ssl_provider" in patch_data or "ssl_cert" in patch_data:
            ssl_cert = patch_data.get("ssl_cert", vhost.ssl_cert)
            if ssl_provider == "upload" and ssl_cert and isinstance(ssl_cert, str):
                patch_data["ssl_expires_at"] = self._parse_cert_expiration(ssl_cert)
            elif ssl_provider == "letsencrypt":
                domain = str(patch_data.get("domain", vhost.domain))
                email = user_email or f"admin@{domain}"
                certbot = CertbotService()
                try:
                    new_cert, new_key = certbot.provision_cert(domain, email)
                    patch_data["ssl_cert"] = new_cert
                    patch_data["ssl_key"] = new_key
                    patch_data["ssl_expires_at"] = self._parse_cert_expiration(new_cert)
                except CertbotError as e:
                    logger.error(f"Failed to provision cert for {domain}: {e}")
                    raise ValueError(f"Let's Encrypt provisioning failed: {e}")

        for field, value in patch_data.items():
            setattr(vhost, field, value)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            if self._is_vhost_domain_unique_violation(error):
                raise VHostDomainAlreadyExistsError from error
            raise

        self.db.refresh(vhost)
        return vhost

    def delete_vhost(self, vhost_id: int) -> None:
        """Delete a vhost if it exists."""
        vhost = self._get_vhost_or_raise(vhost_id)
        self.db.delete(vhost)
        self.db.commit()

    def _get_vhost_or_raise(self, vhost_id: int) -> VHost:
        """Return a vhost by primary key or raise a domain error."""
        vhost = self.db.get(VHost, vhost_id)
        if vhost is None:
            raise VHostNotFoundError
        return vhost

    def _ensure_policy_exists(self, policy_id: object) -> None:
        """Validate policy_id when request points at a concrete policy."""
        if policy_id is not None and self.db.get(Policy, policy_id) is None:
            raise VHostPolicyNotFoundError

    def _validate_patch_data(self, patch_data: dict[str, object]) -> None:
        """Reject nulls for fields that must always keep a real value."""
        for field in NON_NULLABLE_PATCH_FIELDS:
            if field in patch_data and patch_data[field] is None:
                raise VHostFieldCannotBeNullError(field)

    @staticmethod
    def _is_vhost_domain_unique_violation(error: IntegrityError) -> bool:
        """Detect whether IntegrityError comes from duplicate vhost domain."""
        error_text = str(error.orig).lower()
        return "unique" in error_text and "domain" in error_text

    @staticmethod
    def _parse_cert_expiration(cert_pem: str) -> datetime | None:
        try:
            cert = x509.load_pem_x509_certificate(
                cert_pem.encode("utf-8"), default_backend()
            )
            return cert.not_valid_after
        except Exception as e:
            logger.warning(f"Failed to parse certificate: {e}")
            return None
