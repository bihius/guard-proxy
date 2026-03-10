"""Schematy Pydantic dla użytkowników."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Request body dla POST /users.

    Przyjmuje plaintext password — serwis zahashuje go przez bcrypt.
    """

    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.viewer  # domyślnie viewer, nie admin

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        """Hasło musi mieć co najmniej 8 znaków."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserUpdate(BaseModel):
    """Request body dla PATCH /users/{id}.

    Wszystkie pola opcjonalne — PATCH aktualizuje tylko to co podasz.
    Np. możesz wysłać tylko {"full_name": "Jan Kowalski"} żeby zmienić tylko imię.
    """

    email: EmailStr | None = None
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None  # opcjonalna zmiana hasła

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    """Response body dla GET /users i GET /users/{id}.

    CELOWO nie ma tu 'password' ani 'hashed_password'.
    Nigdy nie zwracamy hasła przez API.
    """

    model_config = ConfigDict(from_attributes=True)
    # from_attributes=True → Pydantic umie czytać atrybuty z obiektu SQLAlchemy
    # Bez tego: UserResponse(**user.__dict__) → działa
    # Z tym:    UserResponse.model_validate(user) → działa (czystsze)

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
