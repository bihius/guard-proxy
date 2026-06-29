"""VHost service for vhost domain logic."""

import logging
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.policy import Policy
from app.models.policy_binding import PolicyBinding
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


class PolicyBindingNotFoundError(VHostError):
    """Raised when a policy binding does not exist for the given vhost."""


class PolicyBindingAlreadyExistsError(VHostError):
    """Raised when a policy binding conflicts with an existing binding."""


class PolicyBindingDefaultManagedByVHostError(VHostError):
    """Raised when callers try to manage the legacy default binding directly."""

    def __init__(self) -> None:
        super().__init__(
            "Default root policy binding is managed through vhost.policy_id"
        )


class PolicyBindingFieldCannotBeNullError(VHostError):
    """Raised when a required policy binding field is null."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field '{field_name}' cannot be null")


class PolicyBindingInvalidPathPrefixError(VHostError):
    """Raised when a policy binding path prefix is invalid."""

    def __init__(self) -> None:
        super().__init__("Path prefix must start with /")


class PolicyBindingInvalidPriorityError(VHostError):
    """Raised when a policy binding priority is invalid."""

    def __init__(self) -> None:
        super().__init__("Priority must be greater than or equal to 0")


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
            self.db.flush()
            if policy_id is not None:
                self._sync_default_policy_binding(vhost, policy_id)
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            if self._is_vhost_domain_unique_violation(error):
                raise VHostDomainAlreadyExistsError from error
            raise

        self.db.refresh(vhost)
        return vhost

    def list_vhosts(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        q: str | None = None,
    ) -> tuple[list[VHost], int]:
        """Return a page of vhosts sorted by ID, optionally filtered by domain."""
        query = self.db.query(VHost).options(selectinload(VHost.policy_bindings))

        search = q.strip() if q is not None else None
        if search:
            query = query.filter(VHost.domain.ilike(f"%{search}%"))

        total = query.count()
        items = (
            query.order_by(VHost.id.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def get_vhost(self, vhost_id: int) -> VHost:
        """Return one vhost with related policy loaded."""
        vhost = (
            self.db.query(VHost)
            .options(
                selectinload(VHost.policy),
                selectinload(VHost.policy_bindings),
            )
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
        if "policy_id" in patch_data:
            self._sync_default_policy_binding(vhost, patch_data["policy_id"])

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

    def list_policy_bindings(self, vhost_id: int) -> list[PolicyBinding]:
        """Return all policy bindings for a vhost ordered by priority and ID."""
        self._get_vhost_or_raise(vhost_id)
        return (
            self.db.query(PolicyBinding)
            .filter(PolicyBinding.vhost_id == vhost_id)
            .order_by(PolicyBinding.priority.asc(), PolicyBinding.id.asc())
            .all()
        )

    def create_policy_binding(
        self,
        vhost_id: int,
        *,
        policy_id: int,
        path_prefix: str,
        priority: int,
        comment: str | None,
    ) -> PolicyBinding:
        """Create and persist a path-scoped policy binding for a vhost."""
        self._get_vhost_or_raise(vhost_id)
        self._ensure_policy_exists(policy_id)
        self._validate_policy_binding_fields(
            policy_id=policy_id,
            path_prefix=path_prefix,
            priority=priority,
        )
        if self._is_default_policy_binding(path_prefix, priority):
            raise PolicyBindingDefaultManagedByVHostError()

        binding = PolicyBinding(
            vhost_id=vhost_id,
            policy_id=policy_id,
            path_prefix=path_prefix,
            priority=priority,
            comment=comment,
        )
        self.db.add(binding)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            if self._is_policy_binding_unique_violation(error):
                raise PolicyBindingAlreadyExistsError from error
            raise

        self.db.refresh(binding)
        return binding

    def delete_policy_binding(self, vhost_id: int, binding_id: int) -> None:
        """Delete a policy binding scoped to a vhost."""
        self._get_vhost_or_raise(vhost_id)
        binding = self._get_policy_binding_or_raise(vhost_id, binding_id)
        if self._is_default_policy_binding(binding.path_prefix, binding.priority):
            raise PolicyBindingDefaultManagedByVHostError()
        self.db.delete(binding)
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

    def _get_policy_binding_or_raise(
        self, vhost_id: int, binding_id: int
    ) -> PolicyBinding:
        """Return a binding scoped to a vhost or raise a domain error."""
        binding = (
            self.db.query(PolicyBinding)
            .filter(
                PolicyBinding.vhost_id == vhost_id,
                PolicyBinding.id == binding_id,
            )
            .first()
        )
        if binding is None:
            raise PolicyBindingNotFoundError
        return binding

    def _validate_patch_data(self, patch_data: dict[str, object]) -> None:
        """Reject nulls for fields that must always keep a real value."""
        for field in NON_NULLABLE_PATCH_FIELDS:
            if field in patch_data and patch_data[field] is None:
                raise VHostFieldCannotBeNullError(field)

    def _sync_default_policy_binding(
        self, vhost: VHost, policy_id: object
    ) -> None:
        """Mirror legacy vhost.policy_id into the default root path binding."""
        default_binding = (
            self.db.query(PolicyBinding)
            .filter(
                PolicyBinding.vhost_id == vhost.id,
                PolicyBinding.path_prefix == "/",
                PolicyBinding.priority == 0,
            )
            .first()
        )

        if policy_id is None:
            if default_binding is not None:
                self.db.delete(default_binding)
            return

        if not isinstance(policy_id, int):
            raise PolicyBindingFieldCannotBeNullError("policy_id")

        if default_binding is None:
            self.db.add(
                PolicyBinding(
                    vhost_id=vhost.id,
                    policy_id=policy_id,
                    path_prefix="/",
                    priority=0,
                    comment="Default binding mirrored from vhost.policy_id",
                )
            )
            return

        default_binding.policy_id = policy_id
        if default_binding.comment is None:
            default_binding.comment = "Default binding mirrored from vhost.policy_id"

    def _validate_policy_binding_fields(
        self,
        *,
        policy_id: object,
        path_prefix: object,
        priority: object,
    ) -> None:
        """Validate required policy binding fields before database writes."""
        if policy_id is None:
            raise PolicyBindingFieldCannotBeNullError("policy_id")
        if path_prefix is None:
            raise PolicyBindingFieldCannotBeNullError("path_prefix")
        if priority is None:
            raise PolicyBindingFieldCannotBeNullError("priority")
        if not isinstance(path_prefix, str) or not path_prefix.startswith("/"):
            raise PolicyBindingInvalidPathPrefixError
        if not isinstance(priority, int) or priority < 0:
            raise PolicyBindingInvalidPriorityError

    @staticmethod
    def _is_vhost_domain_unique_violation(error: IntegrityError) -> bool:
        """Detect whether IntegrityError comes from duplicate vhost domain."""
        error_text = str(error.orig).lower()
        return "unique" in error_text and "domain" in error_text

    @staticmethod
    def _is_policy_binding_unique_violation(error: IntegrityError) -> bool:
        """Detect whether IntegrityError comes from duplicate policy binding."""
        error_text = str(error.orig).lower()
        return (
            "uq_policy_bindings_vhost_path_priority" in error_text
            or (
                "unique" in error_text
                and "policy_bindings" in error_text
                and ("path_prefix" in error_text or "vhost_id" in error_text)
            )
        )

    @staticmethod
    def _is_default_policy_binding(path_prefix: str, priority: int) -> bool:
        """Return whether a binding is the legacy vhost.policy_id mirror."""
        return path_prefix == "/" and priority == 0

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
