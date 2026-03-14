"""Auth service — password hashing and JWT token management."""

import logging
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.config import settings
from app.schemas.auth import TokenData

logger = logging.getLogger(__name__)

# CryptContext konfiguruje bcrypt jako algorytm hashowania haseł.
# deprecated="auto" oznacza że stare hashe będą automatycznie oznaczane
# do re-hashowania gdy user się zaloguje (przydatne przy migracji algorytmu).
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Zwraca bcrypt hash hasła.

    Nigdy nie przechowujemy hasła w plaintext — tylko hash.
    bcrypt automatycznie dodaje sól (salt) więc dwa razy zahashowane
    to samo hasło da różne wyniki.
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Weryfikuje czy podane hasło zgadza się z hashem z bazy.

    Zwraca True jeśli hasło poprawne, False jeśli nie.

    Wyjątki są przechwytywane i logowane zamiast propagować — funkcja
    zawsze zwraca bool (fail closed). Rozróżniamy dwa przypadki:
    - ValueError (UnknownHashError) — hash nieznany lub uszkodzony,
      oczekiwany błąd danych, logujemy jako WARNING.
    - RuntimeError (MissingBackendError, InternalBackendError) — problem
      z konfiguracją lub backendem bcrypt, logujemy jako ERROR z traceback.
    """
    try:
        return bool(_pwd_context.verify(plain_password, hashed_password))
    except ValueError:
        # Hash nierozpoznany lub uszkodzony — dane w bazie są nieprawidłowe.
        logger.warning("Password verification failed: unrecognized or malformed hash")
        return False
    except RuntimeError:
        # Brak backendu bcrypt lub błąd wewnętrzny — problem z konfiguracją.
        logger.error("Password verification error: backend failure", exc_info=True)
        return False


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
