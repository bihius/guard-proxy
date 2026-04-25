"""Testy jednostkowe konfiguracji aplikacji (app.config.Settings).

Testujemy walidację zmiennych środowiskowych — szczególnie JWT_SECRET_KEY,
który jest wymagany i nie może być pusty ani składać się tylko ze spacji.

UWAGA: Settings jest singletonem — `settings` na poziomie modułu jest już
zainicjalizowany gdy importujemy app.config. Dlatego tutaj tworzymy nową
instancję Settings bezpośrednio, nadpisując env tylko w scope testu.
"""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

# JWT_SECRET_KEY musi być ustawiony zanim załaduje się settings singleton.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-onlyx")
os.environ.setdefault("LOG_INGEST_SHARED_SECRET", "test-log-ingest-secret")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**env_overrides: str) -> object:
    """Tworzy świeżą instancję Settings z podanymi zmiennymi środowiskowymi.

    Używamy monkeypatching przez os.environ zamiast .env file,
    żeby testy były szybkie i nie zależały od pliku na dysku.
    """
    from app.config import Settings

    # Usuwamy .env file ze ścieżki wyszukiwania żeby nie nadpisywał env vars
    original = dict(os.environ)
    os.environ.update(env_overrides)
    try:
        # env_file=None — ignorujemy .env żeby env vars z os.environ miały pierwszeństwo
        return Settings(_env_file=None)  # type: ignore[call-arg]
    finally:
        # Przywracamy oryginalne zmienne środowiskowe
        os.environ.clear()
        os.environ.update(original)


# ---------------------------------------------------------------------------
# jwt_secret_key — walidacja
# ---------------------------------------------------------------------------


def test_jwt_secret_key_valid() -> None:
    """Poprawny klucz powinien być zaakceptowany."""
    s = _make_settings(
        JWT_SECRET_KEY="moj-super-tajny-klucz",
        LOG_INGEST_SHARED_SECRET="test-log-ingest-secret",
    )
    assert getattr(s, "jwt_secret_key") == "moj-super-tajny-klucz"


def test_jwt_secret_key_empty_raises() -> None:
    """Pusty klucz JWT to luka bezpieczeństwa — powinien rzucić ValidationError."""
    with pytest.raises(ValidationError, match="must not be empty"):
        _make_settings(
            JWT_SECRET_KEY="",
            LOG_INGEST_SHARED_SECRET="test-log-ingest-secret",
        )


def test_jwt_secret_key_whitespace_only_raises() -> None:
    """Klucz złożony tylko ze spacji jest równoważny pustemu — powinien rzucić błąd."""
    with pytest.raises(ValidationError, match="must not be empty"):
        _make_settings(
            JWT_SECRET_KEY="   ",
            LOG_INGEST_SHARED_SECRET="test-log-ingest-secret",
        )


def test_jwt_secret_key_with_spaces_valid() -> None:
    """Klucz z spacjami w środku (ale nie tylko spacje) jest poprawny."""
    s = _make_settings(
        JWT_SECRET_KEY="klucz z spacjami w srodku",
        LOG_INGEST_SHARED_SECRET="test-log-ingest-secret",
    )
    assert getattr(s, "jwt_secret_key") == "klucz z spacjami w srodku"


# ---------------------------------------------------------------------------
# Wartości domyślne
# ---------------------------------------------------------------------------


def test_default_algorithm_is_hs256() -> None:
    s = _make_settings(
        JWT_SECRET_KEY="sekret",
        LOG_INGEST_SHARED_SECRET="test-log-ingest-secret",
    )
    assert getattr(s, "jwt_algorithm") == "HS256"


def test_default_access_token_expire_minutes() -> None:
    s = _make_settings(
        JWT_SECRET_KEY="sekret",
        LOG_INGEST_SHARED_SECRET="test-log-ingest-secret",
    )
    assert getattr(s, "jwt_access_token_expire_minutes") == 30


def test_default_refresh_token_expire_days() -> None:
    s = _make_settings(
        JWT_SECRET_KEY="sekret",
        LOG_INGEST_SHARED_SECRET="test-log-ingest-secret",
    )
    assert getattr(s, "jwt_refresh_token_expire_days") == 7


def test_log_ingest_shared_secret_valid() -> None:
    s = _make_settings(
        JWT_SECRET_KEY="sekret",
        LOG_INGEST_SHARED_SECRET="another-secret",
    )
    assert getattr(s, "log_ingest_shared_secret") == "another-secret"


def test_log_ingest_shared_secret_empty_raises() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        _make_settings(
            JWT_SECRET_KEY="sekret",
            LOG_INGEST_SHARED_SECRET="",
        )


def test_jwt_secret_key_placeholder_raises() -> None:
    with pytest.raises(ValidationError, match="must be replaced"):
        _make_settings(
            JWT_SECRET_KEY="replace-this-with-a-random-secret",
            LOG_INGEST_SHARED_SECRET="test-log-ingest-secret",
        )


def test_log_ingest_shared_secret_placeholder_raises() -> None:
    with pytest.raises(ValidationError, match="must be replaced"):
        _make_settings(
            JWT_SECRET_KEY="real-secret-value",
            LOG_INGEST_SHARED_SECRET="replace-this-with-a-second-random-secret",
        )


def test_auth_refresh_cookie_samesite_none_requires_secure() -> None:
    with pytest.raises(
        ValidationError,
        match="AUTH_REFRESH_COOKIE_SECURE must be true",
    ):
        _make_settings(
            JWT_SECRET_KEY="real-secret-value",
            LOG_INGEST_SHARED_SECRET="real-log-secret",
            AUTH_REFRESH_COOKIE_SAMESITE="none",
            AUTH_REFRESH_COOKIE_SECURE="false",
        )


def test_database_settings_accept_database_url_without_runtime_secrets() -> None:
    from app.config import DatabaseSettings

    original = dict(os.environ)
    os.environ.pop("JWT_SECRET_KEY", None)
    os.environ.pop("LOG_INGEST_SHARED_SECRET", None)
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
    try:
        settings = DatabaseSettings(_env_file=None)  # type: ignore[call-arg]
    finally:
        os.environ.clear()
        os.environ.update(original)

    assert settings.database_url == "sqlite:///./test.db"


def test_settings_reject_empty_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL must not be empty\\."):
        _make_settings(
            JWT_SECRET_KEY="real-secret-value",
            LOG_INGEST_SHARED_SECRET="real-log-secret",
            DATABASE_URL="   ",
        )


def test_settings_ignore_dot_env_example(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("LOG_INGEST_SHARED_SECRET", raising=False)
    (tmp_path / ".env.example").write_text(
        "\n".join(
            [
                "JWT_SECRET_KEY=replace-this-with-a-random-secret",
                "LOG_INGEST_SHARED_SECRET=replace-this-with-a-second-random-secret",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "JWT_SECRET_KEY=real-secret-from-dot-env",
                "LOG_INGEST_SHARED_SECRET=real-log-secret-from-dot-env",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings()

    assert getattr(settings, "jwt_secret_key") == "real-secret-from-dot-env"
    assert (
        getattr(settings, "log_ingest_shared_secret") == "real-log-secret-from-dot-env"
    )
