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
os.environ.setdefault("LOG_INGEST_SHARED_SECRET", "test-log-ingest-secret-for-pytest")

# Ważne sekrety muszą mieć co najmniej 32 znaki i być różne od siebie.
_VALID_JWT_SECRET = "unit-test-jwt-secret-key-0123456789ab"
_VALID_INGEST_SECRET = "unit-test-log-ingest-secret-0123456789ab"


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
        JWT_SECRET_KEY=_VALID_JWT_SECRET,
        LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
    )
    assert getattr(s, "jwt_secret_key") == _VALID_JWT_SECRET


def test_jwt_secret_key_empty_raises() -> None:
    """Pusty klucz JWT to luka bezpieczeństwa — powinien rzucić ValidationError."""
    with pytest.raises(ValidationError, match="must not be empty"):
        _make_settings(
            JWT_SECRET_KEY="",
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
        )


def test_jwt_secret_key_whitespace_only_raises() -> None:
    """Klucz złożony tylko ze spacji jest równoważny pustemu — powinien rzucić błąd."""
    with pytest.raises(ValidationError, match="must not be empty"):
        _make_settings(
            JWT_SECRET_KEY="   ",
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
        )


def test_jwt_secret_key_with_spaces_valid() -> None:
    """Klucz z spacjami w środku (ale nie tylko spacje) jest poprawny."""
    s = _make_settings(
        JWT_SECRET_KEY="klucz z spacjami w srodku i podloga 1234",
        LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
    )
    assert getattr(s, "jwt_secret_key") == "klucz z spacjami w srodku i podloga 1234"


# ---------------------------------------------------------------------------
# Wartości domyślne
# ---------------------------------------------------------------------------


def test_default_algorithm_is_hs256() -> None:
    s = _make_settings(
        JWT_SECRET_KEY=_VALID_JWT_SECRET,
        LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
    )
    assert getattr(s, "jwt_algorithm") == "HS256"


def test_default_access_token_expire_minutes() -> None:
    s = _make_settings(
        JWT_SECRET_KEY=_VALID_JWT_SECRET,
        LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
    )
    assert getattr(s, "jwt_access_token_expire_minutes") == 30


def test_default_refresh_token_expire_days() -> None:
    s = _make_settings(
        JWT_SECRET_KEY=_VALID_JWT_SECRET,
        LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
    )
    assert getattr(s, "jwt_refresh_token_expire_days") == 7


def test_default_auth_refresh_cookie_path_covers_api_prefix() -> None:
    s = _make_settings(
        JWT_SECRET_KEY=_VALID_JWT_SECRET,
        LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
    )
    assert getattr(s, "auth_refresh_cookie_path") == "/"


def test_auth_refresh_cookie_path_must_be_absolute() -> None:
    with pytest.raises(ValidationError, match="AUTH_REFRESH_COOKIE_PATH"):
        _make_settings(
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
            AUTH_REFRESH_COOKIE_PATH="auth",
        )


def test_log_ingest_shared_secret_valid() -> None:
    s = _make_settings(
        JWT_SECRET_KEY=_VALID_JWT_SECRET,
        LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
    )
    assert getattr(s, "log_ingest_shared_secret") == _VALID_INGEST_SECRET


def test_log_ingest_shared_secret_empty_raises() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        _make_settings(
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET="",
        )


def test_jwt_secret_key_placeholder_raises() -> None:
    with pytest.raises(ValidationError, match="must be replaced"):
        _make_settings(
            JWT_SECRET_KEY="replace-this-with-a-random-secret",
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
        )


def test_log_ingest_shared_secret_placeholder_raises() -> None:
    with pytest.raises(ValidationError, match="must be replaced"):
        _make_settings(
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET="replace-this-with-a-second-random-secret",
        )


def test_secret_shorter_than_minimum_length_raises() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        _make_settings(
            JWT_SECRET_KEY="a" * 31,
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
        )


def test_secret_at_minimum_length_is_accepted() -> None:
    secret = "b" * 32
    s = _make_settings(
        JWT_SECRET_KEY=secret,
        LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
    )
    assert getattr(s, "jwt_secret_key") == secret


def test_identical_jwt_and_ingest_secrets_are_rejected() -> None:
    with pytest.raises(
        ValidationError, match="must differ from LOG_INGEST_SHARED_SECRET"
    ):
        _make_settings(
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET=_VALID_JWT_SECRET,
        )


@pytest.mark.parametrize("example", ["docker/.env.example", "release/.env.example"])
def test_secrets_shipped_in_the_example_files_are_rejected(example: str) -> None:
    """Copying an example file must not start the stack with published secrets."""
    repo_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / ".git").exists()
    )
    values: dict[str, str] = {}
    for line in (repo_root / example).read_text(encoding="utf-8").splitlines():
        if line.startswith(("JWT_SECRET_KEY=", "LOG_INGEST_SHARED_SECRET=")):
            name, _, value = line.partition("=")
            values[name] = value

    assert set(values) == {"JWT_SECRET_KEY", "LOG_INGEST_SHARED_SECRET"}, (
        f"{example} must define both secrets"
    )

    for name, value in values.items():
        overrides = {
            "JWT_SECRET_KEY": value if name == "JWT_SECRET_KEY" else _VALID_JWT_SECRET,
            "LOG_INGEST_SHARED_SECRET": (
                value if name == "LOG_INGEST_SHARED_SECRET" else _VALID_INGEST_SECRET
            ),
        }
        with pytest.raises(ValidationError, match="must be replaced"):
            _make_settings(**overrides)


def test_auth_refresh_cookie_samesite_none_requires_secure() -> None:
    with pytest.raises(
        ValidationError,
        match="AUTH_REFRESH_COOKIE_SECURE must be true",
    ):
        _make_settings(
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
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
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
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
                "JWT_SECRET_KEY=real-secret-from-dot-env-0123456789abcd",
                "LOG_INGEST_SHARED_SECRET=real-log-secret-from-dot-env-0123456789ab",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings()

    assert (
        getattr(settings, "jwt_secret_key") == "real-secret-from-dot-env-0123456789abcd"
    )
    assert (
        getattr(settings, "log_ingest_shared_secret")
        == "real-log-secret-from-dot-env-0123456789ab"
    )


def test_settings_reject_empty_haproxy_master_socket_path() -> None:
    with pytest.raises(ValidationError, match="Runtime path settings must not be empty"):
        _make_settings(
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
            HAPROXY_MASTER_SOCKET_PATH="   ",
        )


def test_settings_reject_non_positive_reload_timeout() -> None:
    with pytest.raises(
        ValidationError,
        match="Runtime timeout settings must be greater than zero",
    ):
        _make_settings(
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
            HAPROXY_RELOAD_TIMEOUT_SECONDS="0",
        )


# ---------------------------------------------------------------------------
# GeoIP settings (issue #175)
# ---------------------------------------------------------------------------


def test_geoip_defaults() -> None:
    s = _make_settings(
        JWT_SECRET_KEY=_VALID_JWT_SECRET,
        LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
    )
    assert getattr(s, "geoip_database_url") == "https://downloads.ip66.dev/db/ip66.mmdb"
    assert getattr(s, "geoip_refresh_interval_days") == 1
    assert getattr(s, "geoip_fail_open") is True


def test_geoip_refresh_interval_days_zero_raises() -> None:
    with pytest.raises(
        ValidationError,
        match="GEOIP_REFRESH_INTERVAL_DAYS must be greater than zero",
    ):
        _make_settings(
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
            GEOIP_REFRESH_INTERVAL_DAYS="0",
        )


def test_geoip_database_url_empty_raises() -> None:
    with pytest.raises(
        ValidationError,
        match="GEOIP_DATABASE_URL must not be empty",
    ):
        _make_settings(
            JWT_SECRET_KEY=_VALID_JWT_SECRET,
            LOG_INGEST_SHARED_SECRET=_VALID_INGEST_SECRET,
            GEOIP_DATABASE_URL="   ",
        )
