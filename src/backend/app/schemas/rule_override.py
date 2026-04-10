"""Pydantic schemas for WAF rule overrides."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.rule_override import RuleAction


class RuleOverrideCreate(BaseModel):
    """Request body for POST /policies/{id}/rules."""

    rule_id: int  # OWASP CRS rule number, for example 942100.
    action: RuleAction  # Allowed values: "enable" or "disable".
    comment: str | None = None

    @field_validator("rule_id")
    @classmethod
    def rule_id_must_be_positive(cls, value: int) -> int:
        """Require the rule ID to be a positive integer."""
        if value <= 0:
            raise ValueError("Rule ID must be greater than 0")
        return value


class RuleOverrideUpdate(BaseModel):
    """Request body for PATCH /policies/{id}/rules/{rule_override_id}."""

    rule_id: int | None = None
    action: RuleAction | None = None
    comment: str | None = None

    @field_validator("rule_id")
    @classmethod
    def rule_id_must_be_positive(cls, value: int | None) -> int | None:
        """If rule_id is provided, it must be positive."""
        if value is not None and value <= 0:
            raise ValueError("Rule ID must be greater than 0")
        return value


class RuleOverrideResponse(BaseModel):
    """Response body for GET /policies/{id}/rules."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_id: int
    rule_id: int
    action: RuleAction
    comment: str | None
    created_at: datetime
