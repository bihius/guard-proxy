"""Pydantic schemas for authentication — login and JWT tokens."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    email: EmailStr  # Pydantic validates email format automatically
    password: str


class AccessTokenResponse(BaseModel):
    """Response body for POST /auth/login and POST /auth/refresh.

    access_token — short-lived token (30 min), sent with each request
    token_type   — always "bearer" (OAuth2 standard)

    Refresh token is not returned in JSON — backend sets it as an HttpOnly
    cookie, so frontend JavaScript cannot read it.
    """

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Payload encoded inside JWT token.

    This is NOT sent by API — it is an internal structure decoded
    from token in dependencies.py (get_current_user).

    sub  — "subject" = user ID (JWT standard)
    role — user role (to avoid DB query on every request)
    """

    sub: int  # user ID
    role: str  # "admin" or "viewer"
