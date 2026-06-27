"""Pydantic schemas for WAF custom rules."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.custom_rule import (
    CUSTOM_RULE_ID_MAX,
    CUSTOM_RULE_ID_MIN,
    RuleOperator,
    RulePhase,
)


def _validate_rule_id_range(value: int) -> int:
    """Require the rule ID to fall in the reserved custom rule range."""
    if not (CUSTOM_RULE_ID_MIN <= value <= CUSTOM_RULE_ID_MAX):
        raise ValueError(
            f"Rule ID must be between {CUSTOM_RULE_ID_MIN} and {CUSTOM_RULE_ID_MAX}"
        )
    return value


def _validate_not_blank(value: str, field_label: str) -> str:
    """Require a string field to be non-empty."""
    if not value.strip():
        raise ValueError(f"{field_label} must not be blank")
    return value


def _validate_request_phase(value: RulePhase) -> RulePhase:
    """Allow only phases that run in Guard Proxy's request-only SPOA flow."""
    if value not in {RulePhase.REQUEST_HEADERS, RulePhase.REQUEST_BODY}:
        raise ValueError(
            "Custom rules only support request_headers and request_body phases"
        )
    return value


class CustomRuleCreate(BaseModel):
    """Request body for POST /policies/{id}/custom-rules."""

    rule_id: int  # User-defined rule number, in the reserved custom rule range.
    phase: RulePhase  # SecRule processing phase the rule runs in.
    variables: str  # CRS variables to inspect, for example "ARGS".
    operator: RuleOperator  # Operator used to match the variables.
    operator_argument: str  # The operator's pattern/value, for example a regex.
    actions: str  # Comma-separated SecRule actions, for example "deny,status:403".
    comment: str | None = None
    is_active: bool = True

    @field_validator("rule_id")
    @classmethod
    def rule_id_in_range(cls, value: int) -> int:
        """Require the rule ID to fall in the reserved custom rule range."""
        return _validate_rule_id_range(value)

    @field_validator("phase")
    @classmethod
    def phase_must_be_request_phase(cls, value: RulePhase) -> RulePhase:
        """Reject response/logging phases because Guard Proxy inspects requests only."""
        return _validate_request_phase(value)

    @field_validator("variables")
    @classmethod
    def variables_must_not_be_blank(cls, value: str) -> str:
        """Require the variables field to be a non-empty string."""
        return _validate_not_blank(value, "Variables")

    @field_validator("operator_argument")
    @classmethod
    def operator_argument_must_not_be_blank(cls, value: str) -> str:
        """Require the operator argument to be a non-empty string."""
        return _validate_not_blank(value, "Operator argument")

    @field_validator("actions")
    @classmethod
    def actions_must_not_be_blank(cls, value: str) -> str:
        """Require the actions field to be a non-empty string."""
        return _validate_not_blank(value, "Actions")


class CustomRuleUpdate(BaseModel):
    """Request body for PATCH /policies/{id}/custom-rules/{custom_rule_id}."""

    rule_id: int | None = None
    phase: RulePhase | None = None
    variables: str | None = None
    operator: RuleOperator | None = None
    operator_argument: str | None = None
    actions: str | None = None
    comment: str | None = None
    is_active: bool | None = None

    @field_validator("rule_id")
    @classmethod
    def rule_id_in_range(cls, value: int | None) -> int | None:
        """If rule_id is provided, it must fall in the reserved custom rule range."""
        if value is None:
            return None
        return _validate_rule_id_range(value)

    @field_validator("phase")
    @classmethod
    def phase_must_be_request_phase(cls, value: RulePhase | None) -> RulePhase | None:
        """Reject response/logging phases because Guard Proxy inspects requests only."""
        if value is None:
            return None
        return _validate_request_phase(value)

    @field_validator("variables")
    @classmethod
    def variables_must_not_be_blank(cls, value: str | None) -> str | None:
        """If variables is provided, it must be a non-empty string."""
        if value is None:
            return None
        return _validate_not_blank(value, "Variables")

    @field_validator("operator_argument")
    @classmethod
    def operator_argument_must_not_be_blank(cls, value: str | None) -> str | None:
        """If operator_argument is provided, it must be a non-empty string."""
        if value is None:
            return None
        return _validate_not_blank(value, "Operator argument")

    @field_validator("actions")
    @classmethod
    def actions_must_not_be_blank(cls, value: str | None) -> str | None:
        """If actions is provided, it must be a non-empty string."""
        if value is None:
            return None
        return _validate_not_blank(value, "Actions")


class CustomRuleResponse(BaseModel):
    """Response body for GET /policies/{id}/custom-rules."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_id: int
    rule_id: int
    phase: RulePhase
    variables: str
    operator: RuleOperator
    operator_argument: str
    actions: str
    comment: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
