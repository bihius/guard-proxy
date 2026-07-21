"""Pydantic schemas for WAF policies."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.policy import PolicyEnforcementMode
from app.schemas.custom_rule import CustomRuleResponse
from app.schemas.rule_exclusion import RuleExclusionResponse
from app.schemas.rule_override import RuleOverrideResponse


class PolicyCreate(BaseModel):
    """Request body for POST /policies."""

    name: str
    description: str | None = None
    paranoia_level: int = Field(default=1, ge=1, le=4)
    inbound_anomaly_threshold: int = 5
    outbound_anomaly_threshold: int = 4
    enforcement_mode: PolicyEnforcementMode = PolicyEnforcementMode.block
    ddos_protection_enabled: bool = False
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window_seconds: int = Field(default=10, ge=1, le=3600)
    max_connections_per_ip: int = Field(default=20, ge=1)

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
    ddos_protection_enabled: bool | None = None
    rate_limit_requests: int | None = Field(default=None, ge=1)
    rate_limit_window_seconds: int | None = Field(default=None, ge=1, le=3600)
    max_connections_per_ip: int | None = Field(default=None, ge=1)

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
    ddos_protection_enabled: bool
    rate_limit_requests: int
    rate_limit_window_seconds: int
    max_connections_per_ip: int
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class PolicyDetail(PolicyResponse):
    """Response body for GET /policies/{id} — WITH nested overrides and exclusions.

    Inherits from PolicyResponse and adds a list of rule overrides and exclusions.
    Used only in GET /{id}, because loading relations for list would be slow.
    """

    rule_overrides: list[RuleOverrideResponse] = []
    rule_exclusions: list[RuleExclusionResponse] = []
    custom_rules: list[CustomRuleResponse] = []


class PolicyListResponse(BaseModel):
    """Paginated response returned by GET /policies."""

    items: list[PolicyResponse]
    total: int
    page: int
    per_page: int
