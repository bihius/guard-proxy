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
    """Tworzy krótkotrwały access token JWT (domyślnie 30 minut).

    Payload zawiera:
    - sub  — subject = user ID (standard JWT)
    - role — rola usera
    - type — "access" (odróżnia od refresh tokena)
    - exp  — czas wygaśnięcia (standard JWT)
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
    """Tworzy długotrwały refresh token JWT (domyślnie 7 dni).

    Refresh token zawiera tylko user ID — nie zawiera roli.
    Przy odświeżaniu i tak weryfikujemy usera w bazie (może być nieaktywny).
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
    """Dekoduje i weryfikuje access token JWT.

    Raises:
        jwt.InvalidTokenError — token niepoprawny, wygasły lub zły typ.
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
    """Dekoduje i weryfikuje refresh token JWT. Zwraca user ID.

    Raises:
        jwt.InvalidTokenError — token niepoprawny, wygasły lub zły typ.
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
