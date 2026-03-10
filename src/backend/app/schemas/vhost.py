"""Schematy Pydantic dla wirtualnych hostów (vhosts)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.policy import PolicyResponse


class VHostCreate(BaseModel):
    """Request body dla POST /vhosts."""

    domain: str
    backend_url: str
    description: str | None = None
    ssl_enabled: bool = False
    is_active: bool = True
    policy_id: int | None = None

    @field_validator("domain")
    @classmethod
    def domain_no_protocol(cls, v: str) -> str:
        """Domena nie powinna zawierać protokołu (http:// itp.).

        Poprawne:   "example.com", "sub.example.com"
        Niepoprawne: "http://example.com"
        """
        if v.startswith(("http://", "https://")):
            raise ValueError("Domain should not include protocol (http:// or https://)")
        return v.lower().strip()

    @field_validator("backend_url")
    @classmethod
    def backend_url_has_protocol(cls, v: str) -> str:
        """Backend URL musi zawierać protokół.

        Poprawne:   "http://localhost:3000", "http://192.168.1.10:8080"
        Niepoprawne: "localhost:3000"
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError("Backend URL must start with http:// or https://")
        return v


class VHostUpdate(BaseModel):
    """Request body dla PATCH /vhosts/{id}.

    Wszystkie pola opcjonalne.
    """

    domain: str | None = None
    backend_url: str | None = None
    description: str | None = None
    ssl_enabled: bool | None = None
    is_active: bool | None = None
    policy_id: int | None = None


class VHostResponse(BaseModel):
    """Response body dla GET /vhosts (lista) — BEZ zagnieżdżonej polityki."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    backend_url: str
    description: str | None
    ssl_enabled: bool
    is_active: bool
    policy_id: int | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class VHostDetail(VHostResponse):
    """Response body dla GET /vhosts/{id} — Z zagnieżdżoną polityką.

    Dziedziczy po VHostResponse i dodaje pełny obiekt polityki.
    Zamiast samego policy_id (int), zwracamy cały PolicyResponse.
    """

    policy: PolicyResponse | None = None
