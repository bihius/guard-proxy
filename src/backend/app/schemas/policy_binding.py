"""Pydantic schemas for path-scoped vhost policy bindings."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolicyBindingCreate(BaseModel):
    """Request body for POST /vhosts/{id}/policy-bindings."""

    policy_id: int
    path_prefix: str = Field(default="/", max_length=512)
    priority: int = 0
    comment: str | None = None

    @field_validator("policy_id")
    @classmethod
    def policy_id_must_be_positive(cls, value: int) -> int:
        """Require policy_id to point at a positive primary key."""
        if value <= 0:
            raise ValueError("Policy ID must be greater than 0")
        return value

    @field_validator("path_prefix")
    @classmethod
    def path_prefix_must_start_with_slash(cls, value: str) -> str:
        """Normalize and validate a URL path prefix."""
        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("Path prefix must start with /")
        return value

    @field_validator("priority")
    @classmethod
    def priority_must_be_non_negative(cls, value: int) -> int:
        """Require deterministic non-negative route priority."""
        if value < 0:
            raise ValueError("Priority must be greater than or equal to 0")
        return value


class PolicyBindingResponse(BaseModel):
    """Response body for path-scoped policy bindings."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    vhost_id: int
    policy_id: int
    path_prefix: str
    priority: int
    comment: str | None
    created_at: datetime
    updated_at: datetime
