"""Schematy Pydantic dla nadpisań reguł WAF (rule overrides)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.rule_override import RuleAction


class RuleOverrideCreate(BaseModel):
    """Request body dla POST /policies/{id}/rules."""

    rule_id: int  # numer reguły OWASP CRS, np. 942100
    action: RuleAction  # "enable" lub "disable"
    comment: str | None = None


class RuleOverrideResponse(BaseModel):
    """Response body dla GET /policies/{id}/rules."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_id: int
    rule_id: int
    action: RuleAction
    comment: str | None
    created_at: datetime
