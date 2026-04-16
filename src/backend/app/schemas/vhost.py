"""Pydantic schemas for virtual hosts (vhosts)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.policy import PolicyResponse


class VHostCreate(BaseModel):
    """Request body for POST /vhosts."""

    domain: str
    backend_url: str
    description: str | None = None
    ssl_enabled: bool = False
    is_active: bool = True
    policy_id: int | None = None

    @field_validator("domain")
    @classmethod
    def domain_no_protocol(cls, v: str) -> str:
        """Domain should not contain protocol prefix (http:// etc.).

        strip() before check ensures leading/trailing spaces (e.g. copy-paste)
        do not bypass validation.

        Valid:   "example.com", "sub.example.com"
        Invalid: "http://example.com"
        """
        v = v.strip().lower()
        if v.startswith(("http://", "https://")):
            raise ValueError("Domain should not include protocol (http:// or https://)")
        return v

    @field_validator("backend_url")
    @classmethod
    def backend_url_has_protocol(cls, v: str) -> str:
        """Backend URL must include protocol.

        strip() before check ensures leading/trailing spaces (e.g. copy-paste)
        do not bypass validation.

        Valid:   "http://localhost:3000", "http://192.168.1.10:8080"
        Invalid: "localhost:3000"
        """
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("Backend URL must start with http:// or https://")
        return v


class VHostUpdate(BaseModel):
    """Request body for PATCH /vhosts/{id}.

    All fields are optional.
    """

    domain: str | None = None
    backend_url: str | None = None
    description: str | None = None
    ssl_enabled: bool | None = None
    is_active: bool | None = None
    policy_id: int | None = None

    @field_validator("domain")
    @classmethod
    def domain_no_protocol(cls, v: str | None) -> str | None:
        """If domain is provided in PATCH, validate it exactly like in POST."""
        if v is None:
            return None
        v = v.strip().lower()
        if v.startswith(("http://", "https://")):
            raise ValueError("Domain should not include protocol (http:// or https://)")
        return v

    @field_validator("backend_url")
    @classmethod
    def backend_url_has_protocol(cls, v: str | None) -> str | None:
        """If backend_url is provided in PATCH, it must still include protocol."""
        if v is None:
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("Backend URL must start with http:// or https://")
        return v


class VHostResponse(BaseModel):
    """Response body for GET /vhosts (list) — WITHOUT nested policy."""

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
    """Response body for GET /vhosts/{id} — WITH nested policy.

    Inherits from VHostResponse and adds full policy object.
    Besides policy_id (int), returns full PolicyResponse too.
    """

    policy: PolicyResponse | None = None
