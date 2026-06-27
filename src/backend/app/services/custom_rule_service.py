"""Custom rule service for WAF custom rule domain logic."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.custom_rule import CustomRule, RuleOperator, RulePhase
from app.models.policy import Policy

NON_NULLABLE_PATCH_FIELDS = {
    "rule_id",
    "phase",
    "variables",
    "operator",
    "operator_argument",
    "actions",
    "is_active",
}

# comment is intentionally included: it is nullable and may be set to None.
PATCHABLE_FIELDS = {
    "rule_id",
    "phase",
    "variables",
    "operator",
    "operator_argument",
    "actions",
    "comment",
    "is_active",
}

_UNIQUE_CONSTRAINT = "uq_custom_rules_policy_id_rule_id"


class CustomRuleError(Exception):
    """Base class for custom rule domain errors."""


class CustomRulePolicyNotFoundError(CustomRuleError):
    """Raised when the policy a custom rule is scoped to does not exist."""


class CustomRuleNotFoundError(CustomRuleError):
    """Raised when a custom rule does not exist for the given policy."""


class CustomRuleDuplicateRuleIdError(CustomRuleError):
    """Raised when a policy already has a custom rule with the same rule_id."""


class CustomRuleFieldCannotBeNullError(CustomRuleError):
    """Raised when PATCH sets a non-nullable field to null."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field '{field_name}' cannot be null")


class CustomRuleDisallowedFieldError(CustomRuleError):
    """Raised when PATCH contains a field that is not in the patchable allowlist."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field '{field_name}' cannot be patched")


class CustomRuleService:
    """Encapsulates custom rule CRUD business rules.

    In simple terms:
    - the router should deal with HTTP and auth
    - this service should deal with custom rule rules and database changes
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_custom_rule(
        self,
        policy_id: int,
        *,
        rule_id: int,
        phase: RulePhase,
        variables: str,
        operator: RuleOperator,
        operator_argument: str,
        actions: str,
        comment: str | None,
        is_active: bool,
    ) -> CustomRule:
        """Create and persist a new custom rule for the given policy."""
        self._get_policy_or_raise(policy_id)

        custom_rule = CustomRule(
            policy_id=policy_id,
            rule_id=rule_id,
            phase=phase,
            variables=variables,
            operator=operator,
            operator_argument=operator_argument,
            actions=actions,
            comment=comment,
            is_active=is_active,
        )
        self.db.add(custom_rule)
        self._commit_or_raise_duplicate_rule_id()
        self.db.refresh(custom_rule)
        return custom_rule

    def list_custom_rules(self, policy_id: int) -> list[CustomRule]:
        """Return all custom rules for the given policy, ordered by ID."""
        self._get_policy_or_raise(policy_id)
        return (
            self.db.query(CustomRule)
            .filter(CustomRule.policy_id == policy_id)
            .order_by(CustomRule.id.asc())
            .all()
        )

    def get_custom_rule(self, policy_id: int, custom_rule_id: int) -> CustomRule:
        """Return a single custom rule scoped to the given policy."""
        self._get_policy_or_raise(policy_id)
        return self._get_custom_rule_or_raise(policy_id, custom_rule_id)

    def update_custom_rule(
        self, policy_id: int, custom_rule_id: int, patch_data: dict[str, object]
    ) -> CustomRule:
        """Update selected fields of a custom rule."""
        self._get_policy_or_raise(policy_id)
        custom_rule = self._get_custom_rule_or_raise(policy_id, custom_rule_id)
        self._validate_patch_data(patch_data)

        for field, value in patch_data.items():
            setattr(custom_rule, field, value)

        self._commit_or_raise_duplicate_rule_id()
        self.db.refresh(custom_rule)
        return custom_rule

    def delete_custom_rule(self, policy_id: int, custom_rule_id: int) -> None:
        """Delete a custom rule from a policy."""
        self._get_policy_or_raise(policy_id)
        custom_rule = self._get_custom_rule_or_raise(policy_id, custom_rule_id)
        self.db.delete(custom_rule)
        self.db.commit()

    def _get_policy_or_raise(self, policy_id: int) -> Policy:
        """Return a policy by primary key or raise a domain error."""
        policy = self.db.get(Policy, policy_id)
        if policy is None:
            raise CustomRulePolicyNotFoundError
        return policy

    def _get_custom_rule_or_raise(
        self, policy_id: int, custom_rule_id: int
    ) -> CustomRule:
        """Return a custom rule scoped to a policy or raise a domain error."""
        custom_rule = (
            self.db.query(CustomRule)
            .filter(
                CustomRule.policy_id == policy_id,
                CustomRule.id == custom_rule_id,
            )
            .first()
        )
        if custom_rule is None:
            raise CustomRuleNotFoundError
        return custom_rule

    def _validate_patch_data(self, patch_data: dict[str, object]) -> None:
        """Reject disallowed keys and nulls for non-nullable fields."""
        for field in patch_data:
            if field not in PATCHABLE_FIELDS:
                raise CustomRuleDisallowedFieldError(field)
        for field in NON_NULLABLE_PATCH_FIELDS:
            if field in patch_data and patch_data[field] is None:
                raise CustomRuleFieldCannotBeNullError(field)

    def _commit_or_raise_duplicate_rule_id(self) -> None:
        """Commit changes or convert duplicate rule IDs into a domain error."""
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            if _is_custom_rule_unique_violation(error):
                raise CustomRuleDuplicateRuleIdError from error
            raise


def _is_custom_rule_unique_violation(error: IntegrityError) -> bool:
    """Check whether an IntegrityError comes from a duplicate custom rule ID."""
    error_text = str(error.orig).lower()
    # PostgreSQL includes the constraint name; SQLite includes column names instead.
    return _UNIQUE_CONSTRAINT in error_text or (
        "unique" in error_text
        and "custom_rules" in error_text
        and "rule_id" in error_text
        and "policy_id" in error_text
    )
