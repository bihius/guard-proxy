"""Schematy Pydantic dla autentykacji — logowanie i tokeny JWT."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Request body dla POST /auth/login."""

    email: EmailStr  # Pydantic automatycznie waliduje format emaila
    password: str


class Token(BaseModel):
    """Response body dla POST /auth/login i POST /auth/refresh.

    access_token  — krótkotrwały token (30 min), wysyłany w każdym requeście
    refresh_token — długotrwały token (7 dni), tylko do odświeżania access tokena
    token_type    — zawsze "bearer" (standard OAuth2)
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Payload zakodowany wewnątrz JWT tokena.

    To NIE jest wysyłane przez API — to wewnętrzna struktura
    którą dekodujemy z tokena w dependencies.py (get_current_user).

    sub  — "subject" = user ID (standard JWT)
    role — rola użytkownika (żeby nie pytać DB przy każdym requeście)
    """

    sub: int  # user ID
    role: str  # "admin" lub "viewer"
