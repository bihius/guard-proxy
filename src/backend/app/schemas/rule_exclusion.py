"""Pydantic schemas for WAF rule exclusions."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.rule_exclusion import TARGET_VALUE_PATTERN, TargetType, target_error

# Validated at write time, not only when config is generated: an exclusion the
# generator cannot render is skipped at apply time and silently never applies.


def _validate_target_value_format(value: str) -> str:
    if not value.strip():
        raise ValueError("Target value must not be blank")
    if not TARGET_VALUE_PATTERN.match(value):
        raise ValueError(
            "Target value may only contain letters, digits and _ . : / @ -"
        )
    return value


def _validate_scope_path(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith("/"):
        raise ValueError("Scope path must start with /")
    if "\r" in value or "\n" in value:
        raise ValueError("Scope path must not contain line breaks")
    return value


class RuleExclusionCreate(BaseModel):
    """Request body for POST /policies/{id}/exclusions."""

    rule_id: int  # OWASP CRS rule number, for example 942100.
    target_type: TargetType  # Which CRS variable to narrow inspection on.
    # Collection member, e.g. an argument name; null for single-value targets.
    target_value: str | None = None
    scope_path: str | None = None  # Optional path prefix that scopes the exclusion.
    comment: str | None = None

    @field_validator("rule_id")
    @classmethod
    def rule_id_must_be_positive(cls, value: int) -> int:
        """Require the rule ID to be a positive integer."""
        if value <= 0:
            raise ValueError("Rule ID must be greater than 0")
        return value

    @model_validator(mode="after")
    def target_must_be_renderable(self) -> Self:
        error = target_error(self.target_type, self.target_value)
        if error is not None:
            raise ValueError(error)
        return self

    @field_validator("scope_path")
    @classmethod
    def scope_path_must_be_renderable(cls, value: str | None) -> str | None:
        return _validate_scope_path(value)


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

    # Format only: whether the value fits the target type depends on the
    # stored exclusion, so ExclusionService checks that after merging.
    @field_validator("target_value")
    @classmethod
    def target_value_must_be_renderable(cls, value: str | None) -> str | None:
        return None if value is None else _validate_target_value_format(value)

    @field_validator("scope_path")
    @classmethod
    def scope_path_must_be_renderable(cls, value: str | None) -> str | None:
        return _validate_scope_path(value)


class RuleExclusionResponse(BaseModel):
    """Response body for GET /policies/{id}/exclusions."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_id: int
    rule_id: int
    target_type: TargetType
    target_value: str | None
    scope_path: str | None
    comment: str | None
    created_at: datetime


class RuleExclusionSuggestion(BaseModel):
    """Response body for POST /logs/{log_id}/suggest-exclusion.

    A draft for the admin to review, not a saved exclusion. `target_type` is
    null when the matched variable could not be read from the event or is not
    a supported target type yet; `matched_variable` then says what Coraza
    actually matched, if known. `target_value` is null for single-value
    target types and whenever `target_type` is.
    """

    policy_id: int
    rule_id: int
    target_type: TargetType | None
    target_value: str | None
    scope_path: str | None
    comment: str
    matched_variable: str | None
