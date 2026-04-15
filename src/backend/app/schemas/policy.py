"""Schematy Pydantic dla polityk WAF."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.rule_override import RuleOverrideResponse


class PolicyCreate(BaseModel):
    """Request body dla POST /policies."""

    name: str
    description: str | None = None
    paranoia_level: int = Field(default=1, ge=1, le=4)
    anomaly_threshold: int = 5

    @field_validator("anomaly_threshold")
    @classmethod
    def anomaly_threshold_positive(cls, v: int) -> int:
        """Próg anomaly score musi być dodatni."""
        if v < 1:
            raise ValueError("Anomaly threshold must be at least 1")
        return v


class PolicyUpdate(BaseModel):
    """Request body dla PATCH /policies/{id}.

    Wszystkie pola opcjonalne — PATCH aktualizuje tylko to co podasz.
    """

    name: str | None = None
    description: str | None = None
    paranoia_level: int | None = Field(default=None, ge=1, le=4)
    anomaly_threshold: int | None = None
    is_active: bool | None = None

    @field_validator("anomaly_threshold")
    @classmethod
    def anomaly_threshold_positive(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("Anomaly threshold must be at least 1")
        return v


class PolicyResponse(BaseModel):
    """Response body dla GET /policies (lista) — BEZ rule_overrides."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    paranoia_level: int
    anomaly_threshold: int
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class PolicyDetail(PolicyResponse):
    """Response body dla GET /policies/{id} — Z zagnieżdżonymi rule_overrides.

    Dziedziczy po PolicyResponse i dodaje listę nadpisań reguł.
    Używane tylko w GET /{id} bo ładowanie relacji dla listy byłoby wolne.
    """

    rule_overrides: list[RuleOverrideResponse] = []
