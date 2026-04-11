"""VHost service for vhost domain logic."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.policy import Policy
from app.models.vhost import VHost

NON_NULLABLE_PATCH_FIELDS = {
    "domain",
    "backend_url",
    "ssl_enabled",
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
        is_active: bool,
        policy_id: int | None,
        created_by: int | None,
    ) -> VHost:
        """Create and persist a new vhost."""
        self._ensure_policy_exists(policy_id)

        vhost = VHost(
            domain=domain,
            backend_url=backend_url,
            description=description,
            ssl_enabled=ssl_enabled,
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

    def update_vhost(self, vhost_id: int, patch_data: dict[str, object]) -> VHost:
        """Update selected vhost fields."""
        vhost = self._get_vhost_or_raise(vhost_id)
        self._validate_patch_data(patch_data)

        if "policy_id" in patch_data:
            self._ensure_policy_exists(patch_data["policy_id"])

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
