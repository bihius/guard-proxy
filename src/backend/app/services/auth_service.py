"""Auth service — password hashing and JWT token management."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.config import settings
from app.passwords import hash_password, verify_password
from app.schemas.auth import TokenData

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "decode_refresh_token",
]


def create_access_token(user_id: int, role: str) -> str:
    """Creates short-lived access JWT token (default: 30 minutes).

    Payload contains:
    - sub  — subject = user ID (JWT standard)
    - role — user role
    - type — "access" (distinguishes it from refresh token)
    - exp  — expiration timestamp (JWT standard)
    """
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": expire,
        "jti": str(uuid4()),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: int) -> str:
    """Creates long-lived refresh JWT token (default: 7 days).

    Refresh token contains only user ID — it does not include role.
    During refresh we still verify user in DB (account may be inactive).
    """
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "jti": str(uuid4()),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> TokenData:
    """Decodes and validates access JWT token.

    Raises:
        jwt.InvalidTokenError — invalid token, expired token, or wrong type.
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    try:
        return TokenData(sub=int(payload["sub"]), role=payload["role"])
    except (KeyError, ValueError) as exc:
        raise jwt.InvalidTokenError("Invalid token payload") from exc


def decode_refresh_token(token: str) -> int:
    """Decodes and validates refresh JWT token. Returns user ID.

    Raises:
        jwt.InvalidTokenError — invalid token, expired token, or wrong type.
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Not a refresh token")
    try:
        return int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise jwt.InvalidTokenError("Invalid token payload") from exc
