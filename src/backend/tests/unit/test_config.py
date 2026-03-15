"""Testy jednostkowe konfiguracji aplikacji (app.config.Settings).

Testujemy walidację zmiennych środowiskowych — szczególnie JWT_SECRET_KEY,
który jest wymagany i nie może być pusty ani składać się tylko ze spacji.

UWAGA: Settings jest singletonem — `settings` na poziomie modułu jest już
zainicjalizowany gdy importujemy app.config. Dlatego tutaj tworzymy nową
instancję Settings bezpośrednio, nadpisując env tylko w scope testu.
"""

import os

import pytest
from pydantic import ValidationError

# JWT_SECRET_KEY musi być ustawiony zanim załaduje się settings singleton.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-onlyx")


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
    s = _make_settings(JWT_SECRET_KEY="moj-super-tajny-klucz")
    assert getattr(s, "jwt_secret_key") == "moj-super-tajny-klucz"


def test_jwt_secret_key_empty_raises() -> None:
    """Pusty klucz JWT to luka bezpieczeństwa — powinien rzucić ValidationError."""
    with pytest.raises(ValidationError, match="must not be empty"):
        _make_settings(JWT_SECRET_KEY="")


def test_jwt_secret_key_whitespace_only_raises() -> None:
    """Klucz złożony tylko ze spacji jest równoważny pustemu — powinien rzucić błąd."""
    with pytest.raises(ValidationError, match="must not be empty"):
        _make_settings(JWT_SECRET_KEY="   ")


def test_jwt_secret_key_with_spaces_valid() -> None:
    """Klucz z spacjami w środku (ale nie tylko spacje) jest poprawny."""
    s = _make_settings(JWT_SECRET_KEY="klucz z spacjami w srodku")
    assert getattr(s, "jwt_secret_key") == "klucz z spacjami w srodku"


# ---------------------------------------------------------------------------
# Wartości domyślne
# ---------------------------------------------------------------------------


def test_default_algorithm_is_hs256() -> None:
    s = _make_settings(JWT_SECRET_KEY="sekret")
    assert getattr(s, "jwt_algorithm") == "HS256"


def test_default_access_token_expire_minutes() -> None:
    s = _make_settings(JWT_SECRET_KEY="sekret")
    assert getattr(s, "jwt_access_token_expire_minutes") == 30


def test_default_refresh_token_expire_days() -> None:
    s = _make_settings(JWT_SECRET_KEY="sekret")
    assert getattr(s, "jwt_refresh_token_expire_days") == 7
