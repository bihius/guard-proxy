"""Pydantic schemas for virtual hosts (vhosts)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.policy import PolicyResponse
from app.schemas.policy_binding import PolicyBindingResponse


def _validate_backend_url(value: str) -> str:
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        raise ValueError("Backend URL must start with http:// or https://")
    return value


class VHostBackendBase(BaseModel):
    """Shared backend server fields for vhost requests."""

    url: str = Field(max_length=512)
    is_active: bool = True
    health_check_enabled: bool = True
    health_check_path: str = Field(default="/", max_length=255)
    health_check_interval_seconds: int = Field(default=5, ge=1, le=3600)
    health_check_fall: int = Field(default=3, ge=1, le=100)
    health_check_rise: int = Field(default=2, ge=1, le=100)

    @field_validator("url")
    @classmethod
    def backend_url_has_protocol(cls, value: str) -> str:
        return _validate_backend_url(value)

    @field_validator("health_check_path")
    @classmethod
    def health_check_path_is_absolute(cls, value: str) -> str:
        value = value.strip() or "/"
        if not value.startswith("/"):
            raise ValueError("Health check path must start with /")
        return value


class VHostBackendCreate(VHostBackendBase):
    """Backend server payload for vhost creation."""


class VHostBackendUpdate(VHostBackendBase):
    """Backend server payload for vhost replacement during PATCH."""


class VHostBackendResponse(VHostBackendBase):
    """Backend server response body."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    vhost_id: int
    created_at: datetime
    updated_at: datetime


class VHostCreate(BaseModel):
    """Request body for POST /vhosts."""

    domain: str = Field(max_length=255)
    backend_url: str | None = Field(default=None, max_length=512)
    backends: list[VHostBackendCreate] | None = None
    description: str | None = None
    ssl_enabled: bool = False
    ssl_provider: str = "none"
    ssl_cert: str | None = None
    ssl_key: str | None = None
    is_active: bool = True
    policy_id: int | None = None

    @field_validator("ssl_provider")
    @classmethod
    def validate_ssl_provider(cls, v: str) -> str:
        v = v.lower()
        if v not in ("none", "upload", "letsencrypt"):
            raise ValueError("ssl_provider must be none, upload, or letsencrypt")
        return v

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
    def backend_url_has_protocol(cls, v: str | None) -> str | None:
        """Backend URL must include protocol.

        strip() before check ensures leading/trailing spaces (e.g. copy-paste)
        do not bypass validation.

        Valid:   "http://localhost:3000", "http://192.168.1.10:8080"
        Invalid: "localhost:3000"
        """
        if v is None:
            return None
        return _validate_backend_url(v)

    @model_validator(mode="after")
    def require_backend_target(self) -> "VHostCreate":
        if self.backends is not None and len(self.backends) == 0:
            raise ValueError("At least one backend is required")
        if self.backends is None and self.backend_url is None:
            raise ValueError("Either backend_url or backends is required")
        return self


class VHostUpdate(BaseModel):
    """Request body for PATCH /vhosts/{id}.

    All fields are optional.
    """

    domain: str | None = Field(default=None, max_length=255)
    backend_url: str | None = Field(default=None, max_length=512)
    backends: list[VHostBackendUpdate] | None = None
    description: str | None = None
    ssl_enabled: bool | None = None
    ssl_provider: str | None = None
    ssl_cert: str | None = None
    ssl_key: str | None = None
    is_active: bool | None = None
    policy_id: int | None = None

    @field_validator("ssl_provider")
    @classmethod
    def validate_ssl_provider(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.lower()
        if v not in ("none", "upload", "letsencrypt"):
            raise ValueError("ssl_provider must be none, upload, or letsencrypt")
        return v

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
        return _validate_backend_url(v)

    @model_validator(mode="after")
    def reject_empty_backends(self) -> "VHostUpdate":
        if self.backends is not None and len(self.backends) == 0:
            raise ValueError("At least one backend is required")
        return self


class VHostResponse(BaseModel):
    """Response body for GET /vhosts (list) — WITHOUT nested policy."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    backend_url: str
    backends: list[VHostBackendResponse] = Field(default_factory=list)
    description: str | None
    ssl_enabled: bool
    ssl_provider: str
    ssl_expires_at: datetime | None = None
    is_active: bool
    policy_id: int | None
    policy_bindings: list[PolicyBindingResponse] = Field(default_factory=list)
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class VHostDetail(VHostResponse):
    """Response body for GET /vhosts/{id} — WITH nested policy.

    Inherits from VHostResponse and adds full policy object.
    Besides policy_id (int), returns full PolicyResponse too.
    """

    policy: PolicyResponse | None = None


class VHostListResponse(BaseModel):
    """Paginated response returned by GET /vhosts."""

    items: list[VHostResponse]
    total: int
    page: int
    per_page: int
