"""Pydantic schemas for users."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Request body for POST /users.

    Accepts plaintext password — service hashes it with bcrypt.
    """

    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.viewer  # default is viewer, not admin

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        """Password must be at least 12 characters."""
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        return v


class UserUpdate(BaseModel):
    """Request body for PATCH /users/{id}.

    All fields are optional — PATCH updates only provided fields.
    For example, send only {"full_name": "Jan Kowalski"} to change just the name.
    """

    email: EmailStr | None = None
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None  # optional password change

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        return v


class UserResponse(BaseModel):
    """Response body for GET /users and GET /users/{id}.

    Deliberately does not include 'password' or 'hashed_password'.
    Password must never be returned by API.
    """

    model_config = ConfigDict(from_attributes=True)
    # from_attributes=True -> Pydantic can read attributes from SQLAlchemy object
    # Without this: UserResponse(**user.__dict__) -> works
    # With this:    UserResponse.model_validate(user) -> works (cleaner)

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
