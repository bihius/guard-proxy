"""Pydantic schemas for WAF policies."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.policy import PolicyEnforcementMode
from app.schemas.rule_override import RuleOverrideResponse


class PolicyCreate(BaseModel):
    """Request body for POST /policies."""

    name: str
    description: str | None = None
    paranoia_level: int = Field(default=1, ge=1, le=4)
    inbound_anomaly_threshold: int = 5
    outbound_anomaly_threshold: int = 4
    enforcement_mode: PolicyEnforcementMode = PolicyEnforcementMode.block

    @field_validator("inbound_anomaly_threshold", "outbound_anomaly_threshold")
    @classmethod
    def anomaly_threshold_positive(cls, v: int) -> int:
        """Anomaly score threshold must be positive."""
        if v < 1:
            raise ValueError("Anomaly threshold must be at least 1")
        return v


class PolicyUpdate(BaseModel):
    """Request body for PATCH /policies/{id}.

    All fields are optional — PATCH updates only provided fields.
    """

    name: str | None = None
    description: str | None = None
    paranoia_level: int | None = Field(default=None, ge=1, le=4)
    inbound_anomaly_threshold: int | None = None
    outbound_anomaly_threshold: int | None = None
    enforcement_mode: PolicyEnforcementMode | None = None
    is_active: bool | None = None

    @field_validator("inbound_anomaly_threshold", "outbound_anomaly_threshold")
    @classmethod
    def anomaly_threshold_positive(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("Anomaly threshold must be at least 1")
        return v


class PolicyResponse(BaseModel):
    """Response body for GET /policies (list) — WITHOUT rule_overrides."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    paranoia_level: int
    inbound_anomaly_threshold: int
    outbound_anomaly_threshold: int
    enforcement_mode: PolicyEnforcementMode
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class PolicyDetail(PolicyResponse):
    """Response body for GET /policies/{id} — WITH nested rule_overrides.

    Inherits from PolicyResponse and adds a list of rule overrides.
    Used only in GET /{id}, because loading relations for list would be slow.
    """

    rule_overrides: list[RuleOverrideResponse] = []
