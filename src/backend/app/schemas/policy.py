"""Pydantic schemas for WAF policies."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants.countries import VALID_COUNTRY_CODES
from app.models.policy import PolicyEnforcementMode, PolicyGeoipMode
from app.schemas.custom_rule import CustomRuleResponse
from app.schemas.rule_exclusion import RuleExclusionResponse
from app.schemas.rule_override import RuleOverrideResponse


def _normalize_and_validate_countries(codes: list[str]) -> list[str]:
    """Uppercase/strip, drop empties, de-duplicate (first-seen order kept).

    Raises ValueError for any code not in VALID_COUNTRY_CODES. "ZZ" is
    explicitly rejected — it is an internal sentinel for unresolved GeoIP
    database records, not an admin-selectable country.
    """
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in codes:
        code = raw.strip().upper()
        if not code:
            continue
        if code == "ZZ" or code not in VALID_COUNTRY_CODES:
            raise ValueError(f"Unknown country code: {code}")
        if code not in seen:
            seen.add(code)
            normalized.append(code)
    return normalized


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
    auto_ban_enabled: bool = False
    ban_threshold: int = Field(default=10, ge=1)
    ban_duration_seconds: int = Field(default=600, ge=1, le=86400)
    geoip_mode: PolicyGeoipMode = PolicyGeoipMode.off
    geoip_countries: list[str] = Field(default_factory=list, max_length=250)

    @field_validator("inbound_anomaly_threshold", "outbound_anomaly_threshold")
    @classmethod
    def anomaly_threshold_positive(cls, v: int) -> int:
        """Anomaly score threshold must be positive."""
        if v < 1:
            raise ValueError("Anomaly threshold must be at least 1")
        return v

    @field_validator("geoip_countries")
    @classmethod
    def geoip_countries_valid(cls, v: list[str]) -> list[str]:
        return _normalize_and_validate_countries(v)


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
    auto_ban_enabled: bool | None = None
    ban_threshold: int | None = Field(default=None, ge=1)
    ban_duration_seconds: int | None = Field(default=None, ge=1, le=86400)
    # geoip_mode/geoip_countries are validated independently here (format and
    # known-code checks only). The cross-field rule "geoip_countries must be
    # non-empty when geoip_mode != off" is intentionally NOT a schema
    # validator: PATCH is partial and this schema cannot see the row's
    # currently stored values, so that rule lives in
    # app.services.policy_service._validate_geoip instead. Do not "fix" this
    # by adding a model_validator here.
    geoip_mode: PolicyGeoipMode | None = None
    geoip_countries: list[str] | None = Field(default=None, max_length=250)

    @field_validator("inbound_anomaly_threshold", "outbound_anomaly_threshold")
    @classmethod
    def anomaly_threshold_positive(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("Anomaly threshold must be at least 1")
        return v

    @field_validator("geoip_countries")
    @classmethod
    def geoip_countries_valid(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return _normalize_and_validate_countries(v)


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
    auto_ban_enabled: bool
    ban_threshold: int
    ban_duration_seconds: int
    geoip_mode: PolicyGeoipMode
    geoip_countries: list[str]
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
