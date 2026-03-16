"""Testy jednostkowe serwisu auth (app.services.auth_service).

Testy są izolowane — bez bazy danych, bez aplikacji FastAPI, bez HTTP.
Testujemy czyste funkcje: hashowanie haseł, tworzenie tokenów, dekodowanie tokenów.
"""

import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-onlyx")

import jwt  # noqa: E402

from app.services.auth_service import (  # noqa: E402
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

# ---------------------------------------------------------------------------
# hash_password
# ---------------------------------------------------------------------------


def test_hash_password_returns_string() -> None:
    result = hash_password("somesecret")
    assert isinstance(result, str)


def test_hash_password_not_plaintext() -> None:
    result = hash_password("somesecret")
    assert result != "somesecret"


def test_hash_password_different_salts() -> None:
    """bcrypt dodaje losową sól, więc zahashowanie tego samego hasła
    dwa razy daje różne wyniki.
    """
    h1 = hash_password("somesecret")
    h2 = hash_password("somesecret")
    assert h1 != h2


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------


def test_verify_password_correct() -> None:
    h = hash_password("correcthorse")
    assert verify_password("correcthorse", h) is True


def test_verify_password_wrong() -> None:
    h = hash_password("correcthorse")
    assert verify_password("wrongpassword", h) is False


def test_verify_password_corrupt_hash_returns_false(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Uszkodzony hash w bazie powinien zwrócić False i zalogować ostrzeżenie,
    nie rzucać wyjątkiem (zachowanie fail-closed).
    """
    import logging

    with caplog.at_level(logging.WARNING, logger="app.services.auth_service"):
        result = verify_password("anypassword", "not-a-valid-bcrypt-hash")
    assert result is False
    assert any(
        "malformed" in r.message or "unrecognized" in r.message for r in caplog.records
    )


# ---------------------------------------------------------------------------
# create_access_token / decode_access_token
# ---------------------------------------------------------------------------


def test_create_access_token_is_string() -> None:
    token = create_access_token(user_id=1, role="admin")
    assert isinstance(token, str)


def test_decode_access_token_round_trip() -> None:
    token = create_access_token(user_id=42, role="viewer")
    data = decode_access_token(token)
    assert data.sub == 42
    assert data.role == "viewer"


def test_decode_access_token_has_type_access() -> None:
    """decode_access_token musi odrzucać tokeny z typem innym niż 'access'."""
    # Tworzymy refresh token i próbujemy zdekodować go jako access — musi się nie udać.
    refresh = create_refresh_token(user_id=1)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(refresh)


def test_decode_access_token_expired() -> None:
    from datetime import UTC, datetime, timedelta

    from app.config import settings

    payload = {
        "sub": "1",
        "role": "admin",
        "type": "access",
        "exp": datetime.now(UTC) - timedelta(seconds=1),
    }
    expired_token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(expired_token)


def test_decode_access_token_bad_signature() -> None:
    token = create_access_token(user_id=1, role="admin")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token + "tampered")


def test_decode_access_token_missing_sub() -> None:
    from app.config import settings

    payload = {"role": "admin", "type": "access"}
    token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_decode_access_token_missing_role() -> None:
    from app.config import settings

    payload = {"sub": "1", "type": "access"}
    token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


# ---------------------------------------------------------------------------
# create_refresh_token / decode_refresh_token
# ---------------------------------------------------------------------------


def test_create_refresh_token_is_string() -> None:
    token = create_refresh_token(user_id=7)
    assert isinstance(token, str)


def test_decode_refresh_token_round_trip() -> None:
    token = create_refresh_token(user_id=99)
    user_id = decode_refresh_token(token)
    assert user_id == 99


def test_decode_refresh_token_rejects_access_token() -> None:
    """decode_refresh_token musi odrzucać tokeny z typem innym niż 'refresh'."""
    access = create_access_token(user_id=1, role="admin")
    with pytest.raises(jwt.InvalidTokenError):
        decode_refresh_token(access)


def test_decode_refresh_token_expired() -> None:
    from datetime import UTC, datetime, timedelta

    from app.config import settings

    payload = {
        "sub": "5",
        "type": "refresh",
        "exp": datetime.now(UTC) - timedelta(seconds=1),
    }
    expired_token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_refresh_token(expired_token)


def test_refresh_token_has_no_role() -> None:
    """Refresh tokeny celowo nie zawierają pola 'role' — weryfikujemy payload."""
    from app.config import settings

    token = create_refresh_token(user_id=3)
    payload = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    assert "role" not in payload
    assert payload["type"] == "refresh"
