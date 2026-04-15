"""Policy service for WAF policy domain logic."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.policy import Policy

NON_NULLABLE_PATCH_FIELDS = {
    "name",
    "paranoia_level",
    "anomaly_threshold",
    "is_active",
}

# description is intentionally included: it is nullable and may be set to None.
PATCHABLE_FIELDS = {
    "name",
    "description",
    "paranoia_level",
    "anomaly_threshold",
    "is_active",
}


class PolicyError(Exception):
    """Base class for policy domain errors."""


class PolicyNotFoundError(PolicyError):
    """Raised when a policy does not exist."""


class PolicyNameAlreadyExistsError(PolicyError):
    """Raised when a policy name conflicts with an existing row."""


class PolicyFieldCannotBeNullError(PolicyError):
    """Raised when PATCH sets a non-nullable field to null."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field '{field_name}' cannot be null")


class PolicyDisallowedFieldError(PolicyError):
    """Raised when PATCH contains a field that is not in the patchable allowlist."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field '{field_name}' cannot be patched")


class PolicyDatabaseConstraintError(PolicyError):
    """Raised when an IntegrityError occurs for a reason other than a duplicate name."""


class PolicyService:
    """Encapsulates policy CRUD business rules.

    In simple terms:
    - the router should deal with HTTP and auth
    - this service should deal with policy rules and database changes
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_policy(
        self,
        *,
        name: str,
        description: str | None,
        paranoia_level: int,
        anomaly_threshold: int,
        created_by: int | None,
    ) -> Policy:
        """Create and persist a new policy."""
        policy = Policy(
            name=name,
            description=description,
            paranoia_level=paranoia_level,
            anomaly_threshold=anomaly_threshold,
            is_active=True,
            created_by=created_by,
        )
        self.db.add(policy)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            if self._is_policy_name_unique_violation(error):
                raise PolicyNameAlreadyExistsError from error
            raise PolicyDatabaseConstraintError from error

        self.db.refresh(policy)
        return policy

    def list_policies(self) -> list[Policy]:
        """Return all policies sorted by ID."""
        return self.db.query(Policy).order_by(Policy.id.asc()).all()

    def get_policy(self, policy_id: int) -> Policy:
        """Return one policy with related rule overrides loaded."""
        policy = (
            self.db.query(Policy)
            .options(selectinload(Policy.rule_overrides))
            .filter(Policy.id == policy_id)
            .first()
        )
        if policy is None:
            raise PolicyNotFoundError
        return policy

    def update_policy(self, policy_id: int, patch_data: dict[str, object]) -> Policy:
        """Update selected policy fields."""
        policy = self._get_policy_or_raise(policy_id)
        self._validate_patch_data(patch_data)

        for field, value in patch_data.items():
            setattr(policy, field, value)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            if self._is_policy_name_unique_violation(error):
                raise PolicyNameAlreadyExistsError from error
            raise PolicyDatabaseConstraintError from error

        self.db.refresh(policy)
        return policy

    def delete_policy(self, policy_id: int) -> None:
        """Delete a policy if it exists."""
        policy = self._get_policy_or_raise(policy_id)
        self.db.delete(policy)
        self.db.commit()

    def _get_policy_or_raise(self, policy_id: int) -> Policy:
        """Return a policy by primary key or raise a domain error."""
        policy = self.db.get(Policy, policy_id)
        if policy is None:
            raise PolicyNotFoundError
        return policy

    def _validate_patch_data(self, patch_data: dict[str, object]) -> None:
        """Reject disallowed keys and nulls for non-nullable fields."""
        for field in patch_data:
            if field not in PATCHABLE_FIELDS:
                raise PolicyDisallowedFieldError(field)
        for field in NON_NULLABLE_PATCH_FIELDS:
            if field in patch_data and patch_data[field] is None:
                raise PolicyFieldCannotBeNullError(field)

    @staticmethod
    def _is_policy_name_unique_violation(error: IntegrityError) -> bool:
        """Detect whether IntegrityError comes from duplicate policy name."""
        error_text = str(error.orig).lower()
        return "unique" in error_text and "name" in error_text
