"""Exclusion service for WAF rule exclusion domain logic."""

from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.models.rule_exclusion import RuleExclusion, TargetType

NON_NULLABLE_PATCH_FIELDS = {"rule_id", "target_type", "target_value"}

# scope_path and comment are intentionally included: they are nullable and may be
# set to None.
PATCHABLE_FIELDS = {
    "rule_id",
    "target_type",
    "target_value",
    "scope_path",
    "comment",
}


class ExclusionError(Exception):
    """Base class for rule exclusion domain errors."""


class ExclusionPolicyNotFoundError(ExclusionError):
    """Raised when the policy a rule exclusion is scoped to does not exist."""


class ExclusionNotFoundError(ExclusionError):
    """Raised when a rule exclusion does not exist for the given policy."""


class ExclusionFieldCannotBeNullError(ExclusionError):
    """Raised when PATCH sets a non-nullable field to null."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field '{field_name}' cannot be null")


class ExclusionDisallowedFieldError(ExclusionError):
    """Raised when PATCH contains a field that is not in the patchable allowlist."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field '{field_name}' cannot be patched")


class ExclusionService:
    """Encapsulates rule exclusion CRUD business rules.

    In simple terms:
    - the router should deal with HTTP and auth
    - this service should deal with exclusion rules and database changes
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_exclusion(
        self,
        policy_id: int,
        *,
        rule_id: int,
        target_type: TargetType,
        target_value: str,
        scope_path: str | None,
        comment: str | None,
    ) -> RuleExclusion:
        """Create and persist a new rule exclusion for the given policy."""
        self._get_policy_or_raise(policy_id)

        exclusion = RuleExclusion(
            policy_id=policy_id,
            rule_id=rule_id,
            target_type=target_type,
            target_value=target_value,
            scope_path=scope_path,
            comment=comment,
        )
        self.db.add(exclusion)
        self.db.commit()
        self.db.refresh(exclusion)
        return exclusion

    def list_exclusions(self, policy_id: int) -> list[RuleExclusion]:
        """Return all rule exclusions for the given policy, ordered by ID."""
        self._get_policy_or_raise(policy_id)
        return (
            self.db.query(RuleExclusion)
            .filter(RuleExclusion.policy_id == policy_id)
            .order_by(RuleExclusion.id.asc())
            .all()
        )

    def get_exclusion(self, policy_id: int, exclusion_id: int) -> RuleExclusion:
        """Return a single rule exclusion scoped to the given policy."""
        self._get_policy_or_raise(policy_id)
        return self._get_exclusion_or_raise(policy_id, exclusion_id)

    def update_exclusion(
        self, policy_id: int, exclusion_id: int, patch_data: dict[str, object]
    ) -> RuleExclusion:
        """Update selected fields of a rule exclusion."""
        self._get_policy_or_raise(policy_id)
        exclusion = self._get_exclusion_or_raise(policy_id, exclusion_id)
        self._validate_patch_data(patch_data)

        for field, value in patch_data.items():
            setattr(exclusion, field, value)

        self.db.commit()
        self.db.refresh(exclusion)
        return exclusion

    def delete_exclusion(self, policy_id: int, exclusion_id: int) -> None:
        """Delete a rule exclusion from a policy."""
        self._get_policy_or_raise(policy_id)
        exclusion = self._get_exclusion_or_raise(policy_id, exclusion_id)
        self.db.delete(exclusion)
        self.db.commit()

    def _get_policy_or_raise(self, policy_id: int) -> Policy:
        """Return a policy by primary key or raise a domain error."""
        policy = self.db.get(Policy, policy_id)
        if policy is None:
            raise ExclusionPolicyNotFoundError
        return policy

    def _get_exclusion_or_raise(
        self, policy_id: int, exclusion_id: int
    ) -> RuleExclusion:
        """Return an exclusion scoped to a policy or raise a domain error."""
        exclusion = (
            self.db.query(RuleExclusion)
            .filter(
                RuleExclusion.policy_id == policy_id,
                RuleExclusion.id == exclusion_id,
            )
            .first()
        )
        if exclusion is None:
            raise ExclusionNotFoundError
        return exclusion

    def _validate_patch_data(self, patch_data: dict[str, object]) -> None:
        """Reject disallowed keys and nulls for non-nullable fields."""
        for field in patch_data:
            if field not in PATCHABLE_FIELDS:
                raise ExclusionDisallowedFieldError(field)
        for field in NON_NULLABLE_PATCH_FIELDS:
            if field in patch_data and patch_data[field] is None:
                raise ExclusionFieldCannotBeNullError(field)
