"""Testy jednostkowe schematów Pydantic.

Testujemy walidację danych wejściowych — bez bazy danych, bez HTTP.
Pydantic waliduje dane przy tworzeniu obiektu, więc wystarczy sprawdzić
czy ValidationError jest rzucany przy złych danych.
"""

import os

import pytest
from pydantic import ValidationError

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-onlyx")

from app.schemas.policy import PolicyCreate, PolicyUpdate  # noqa: E402
from app.schemas.user import UserCreate, UserUpdate  # noqa: E402
from app.schemas.vhost import VHostCreate  # noqa: E402

# ---------------------------------------------------------------------------
# UserCreate
# ---------------------------------------------------------------------------


def test_user_create_valid() -> None:
    u = UserCreate(email="jan@example.com", password="supersecret123", full_name="Jan")
    assert u.email == "jan@example.com"


def test_user_create_password_too_short() -> None:
    """Hasło krótsze niż 12 znaków powinno rzucić ValidationError."""
    with pytest.raises(ValidationError, match="at least 12 characters"):
        UserCreate(email="jan@example.com", password="short", full_name="Jan")


def test_user_create_password_exactly_12() -> None:
    """Dokładnie 12 znaków to minimum — powinno przejść."""
    u = UserCreate(email="jan@example.com", password="a" * 12, full_name="Jan")
    assert len(u.password) == 12


def test_user_create_invalid_email() -> None:
    """Niepoprawny adres email powinien rzucić ValidationError."""
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="supersecret123", full_name="Jan")


def test_user_create_default_role_is_viewer() -> None:
    """Domyślna rola to viewer — nie admin."""
    from app.models.user import UserRole

    u = UserCreate(email="jan@example.com", password="supersecret123", full_name="Jan")
    assert u.role == UserRole.viewer


# ---------------------------------------------------------------------------
# UserUpdate
# ---------------------------------------------------------------------------


def test_user_update_all_none_is_valid() -> None:
    """PATCH bez żadnych pól to poprawny request."""
    u = UserUpdate()
    assert u.password is None
    assert u.email is None


def test_user_update_password_none_is_valid() -> None:
    """Brak zmiany hasła (None) nie powinien rzucać błędu."""
    u = UserUpdate(full_name="Nowe Imię")
    assert u.password is None


def test_user_update_password_too_short() -> None:
    """Jeśli podano hasło, też musi mieć minimum 12 znaków."""
    with pytest.raises(ValidationError, match="at least 12 characters"):
        UserUpdate(password="tooshort")


def test_user_update_password_valid() -> None:
    u = UserUpdate(password="nowehashlo123")
    assert u.password == "nowehashlo123"


# ---------------------------------------------------------------------------
# PolicyCreate
# ---------------------------------------------------------------------------


def test_policy_create_valid() -> None:
    p = PolicyCreate(name="default", paranoia_level=2, anomaly_threshold=10)
    assert p.paranoia_level == 2


def test_policy_create_paranoia_level_zero() -> None:
    """Paranoia level 0 jest poza zakresem 1–4."""
    with pytest.raises(ValidationError, match="between 1 and 4"):
        PolicyCreate(name="x", paranoia_level=0)


def test_policy_create_paranoia_level_five() -> None:
    """Paranoia level 5 jest poza zakresem 1–4."""
    with pytest.raises(ValidationError, match="between 1 and 4"):
        PolicyCreate(name="x", paranoia_level=5)


def test_policy_create_paranoia_level_boundaries() -> None:
    """Granice zakresu 1 i 4 powinny przejść walidację."""
    p1 = PolicyCreate(name="x", paranoia_level=1)
    p4 = PolicyCreate(name="x", paranoia_level=4)
    assert p1.paranoia_level == 1
    assert p4.paranoia_level == 4


def test_policy_create_anomaly_threshold_zero() -> None:
    """Próg anomalii 0 jest niepoprawny — musi być co najmniej 1."""
    with pytest.raises(ValidationError, match="at least 1"):
        PolicyCreate(name="x", anomaly_threshold=0)


def test_policy_create_anomaly_threshold_negative() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        PolicyCreate(name="x", anomaly_threshold=-5)


def test_policy_create_anomaly_threshold_one_valid() -> None:
    p = PolicyCreate(name="x", anomaly_threshold=1)
    assert p.anomaly_threshold == 1


# ---------------------------------------------------------------------------
# PolicyUpdate — pola opcjonalne, ale walidowane gdy podane
# ---------------------------------------------------------------------------


def test_policy_update_paranoia_none_valid() -> None:
    p = PolicyUpdate(name="nowa nazwa")
    assert p.paranoia_level is None


def test_policy_update_paranoia_invalid() -> None:
    with pytest.raises(ValidationError, match="between 1 and 4"):
        PolicyUpdate(paranoia_level=99)


def test_policy_update_anomaly_zero_invalid() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        PolicyUpdate(anomaly_threshold=0)


# ---------------------------------------------------------------------------
# VHostCreate
# ---------------------------------------------------------------------------


def test_vhost_create_valid() -> None:
    v = VHostCreate(domain="example.com", backend_url="http://localhost:8080")
    assert v.domain == "example.com"
    assert v.backend_url == "http://localhost:8080"


def test_vhost_create_domain_with_http_invalid() -> None:
    """Domena nie powinna zawierać protokołu."""
    with pytest.raises(ValidationError, match="should not include protocol"):
        VHostCreate(domain="http://example.com", backend_url="http://localhost:8080")


def test_vhost_create_domain_with_https_invalid() -> None:
    with pytest.raises(ValidationError, match="should not include protocol"):
        VHostCreate(domain="https://example.com", backend_url="http://localhost:8080")


def test_vhost_create_domain_lowercased() -> None:
    """Domena jest normalizowana do lowercase."""
    v = VHostCreate(domain="EXAMPLE.COM", backend_url="http://localhost:8080")
    assert v.domain == "example.com"


def test_vhost_create_domain_stripped() -> None:
    """Spacje wokół domeny są usuwane przed walidacją."""
    v = VHostCreate(domain="  example.com  ", backend_url="http://localhost:8080")
    assert v.domain == "example.com"


def test_vhost_create_backend_url_without_protocol_invalid() -> None:
    """Backend URL bez protokołu jest niepoprawny."""
    with pytest.raises(ValidationError, match="must start with http"):
        VHostCreate(domain="example.com", backend_url="localhost:8080")


def test_vhost_create_backend_url_https_valid() -> None:
    v = VHostCreate(domain="example.com", backend_url="https://backend.internal:443")
    assert v.backend_url == "https://backend.internal:443"


def test_vhost_create_backend_url_stripped() -> None:
    """Spacje wokół backend URL są usuwane."""
    v = VHostCreate(domain="example.com", backend_url="  http://localhost:8080  ")
    assert v.backend_url == "http://localhost:8080"
