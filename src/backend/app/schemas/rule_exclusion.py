"""Pydantic schemas for WAF rule exclusions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.rule_exclusion import TargetType


class RuleExclusionCreate(BaseModel):
    """Request body for POST /policies/{id}/exclusions."""

    rule_id: int  # OWASP CRS rule number, for example 942100.
    target_type: TargetType  # Which CRS variable to narrow inspection on.
    target_value: str  # The specific target, for example an argument name.
    scope_path: str | None = None  # Optional path prefix that scopes the exclusion.
    comment: str | None = None

    @field_validator("rule_id")
    @classmethod
    def rule_id_must_be_positive(cls, value: int) -> int:
        """Require the rule ID to be a positive integer."""
        if value <= 0:
            raise ValueError("Rule ID must be greater than 0")
        return value

    @field_validator("target_value")
    @classmethod
    def target_value_must_not_be_blank(cls, value: str) -> str:
        """Require the target value to be a non-empty string."""
        if not value.strip():
            raise ValueError("Target value must not be blank")
        return value


class RuleExclusionUpdate(BaseModel):
    """Request body for PATCH /policies/{id}/exclusions/{rule_exclusion_id}."""

    rule_id: int | None = None
    target_type: TargetType | None = None
    target_value: str | None = None
    scope_path: str | None = None
    comment: str | None = None

    @field_validator("rule_id")
    @classmethod
    def rule_id_must_be_positive(cls, value: int | None) -> int | None:
        """If rule_id is provided, it must be positive."""
        if value is not None and value <= 0:
            raise ValueError("Rule ID must be greater than 0")
        return value

    @field_validator("target_value")
    @classmethod
    def target_value_must_not_be_blank(cls, value: str | None) -> str | None:
        """If target_value is provided, it must be a non-empty string."""
        if value is not None and not value.strip():
            raise ValueError("Target value must not be blank")
        return value


class RuleExclusionResponse(BaseModel):
    """Response body for GET /policies/{id}/exclusions."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_id: int
    rule_id: int
    target_type: TargetType
    target_value: str
    scope_path: str | None
    comment: str | None
    created_at: datetime
