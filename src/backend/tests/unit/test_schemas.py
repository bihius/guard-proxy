"""Unit tests for Pydantic schemas.

These tests focus on input validation without a database or HTTP layer.
Pydantic validates data when the object is created, so it is enough to
check whether ValidationError is raised for invalid input.
"""

import os

import pytest
from pydantic import ValidationError

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-onlyx")

from app.models.rule_override import RuleAction  # noqa: E402
from app.schemas.policy import PolicyCreate, PolicyUpdate  # noqa: E402
from app.schemas.rule_override import (  # noqa: E402
    RuleOverrideCreate,
    RuleOverrideUpdate,
)
from app.schemas.user import UserCreate, UserUpdate  # noqa: E402
from app.schemas.vhost import VHostCreate  # noqa: E402

# ---------------------------------------------------------------------------
# UserCreate
# ---------------------------------------------------------------------------


def test_user_create_valid() -> None:
    u = UserCreate(email="jan@example.com", password="supersecret123", full_name="Jan")
    assert u.email == "jan@example.com"


def test_user_create_password_too_short() -> None:
    """A password shorter than 12 characters should raise ValidationError."""
    with pytest.raises(ValidationError, match="at least 12 characters"):
        UserCreate(email="jan@example.com", password="short", full_name="Jan")


def test_user_create_password_exactly_12() -> None:
    """Exactly 12 characters is the minimum and should pass."""
    u = UserCreate(email="jan@example.com", password="a" * 12, full_name="Jan")
    assert len(u.password) == 12


def test_user_create_invalid_email() -> None:
    """An invalid email address should raise ValidationError."""
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="supersecret123", full_name="Jan")


def test_user_create_default_role_is_viewer() -> None:
    """The default role should be viewer, not admin."""
    from app.models.user import UserRole

    u = UserCreate(email="jan@example.com", password="supersecret123", full_name="Jan")
    assert u.role == UserRole.viewer


# ---------------------------------------------------------------------------
# UserUpdate
# ---------------------------------------------------------------------------


def test_user_update_all_none_is_valid() -> None:
    """PATCH with no fields is a valid request."""
    u = UserUpdate()
    assert u.password is None
    assert u.email is None


def test_user_update_password_none_is_valid() -> None:
    """Not changing the password (None) should not raise an error."""
    u = UserUpdate(full_name="Nowe Imię")
    assert u.password is None


def test_user_update_password_too_short() -> None:
    """If a password is provided, it must still be at least 12 characters."""
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
    """Paranoia level 0 is outside the allowed 1-4 range."""
    with pytest.raises(ValidationError, match="between 1 and 4"):
        PolicyCreate(name="x", paranoia_level=0)


def test_policy_create_paranoia_level_five() -> None:
    """Paranoia level 5 is outside the allowed 1-4 range."""
    with pytest.raises(ValidationError, match="between 1 and 4"):
        PolicyCreate(name="x", paranoia_level=5)


def test_policy_create_paranoia_level_boundaries() -> None:
    """Boundary values 1 and 4 should pass validation."""
    p1 = PolicyCreate(name="x", paranoia_level=1)
    p4 = PolicyCreate(name="x", paranoia_level=4)
    assert p1.paranoia_level == 1
    assert p4.paranoia_level == 4


def test_policy_create_anomaly_threshold_zero() -> None:
    """An anomaly threshold of 0 is invalid; it must be at least 1."""
    with pytest.raises(ValidationError, match="at least 1"):
        PolicyCreate(name="x", anomaly_threshold=0)


def test_policy_create_anomaly_threshold_negative() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        PolicyCreate(name="x", anomaly_threshold=-5)


def test_policy_create_anomaly_threshold_one_valid() -> None:
    p = PolicyCreate(name="x", anomaly_threshold=1)
    assert p.anomaly_threshold == 1


# ---------------------------------------------------------------------------
# PolicyUpdate: optional fields, but still validated when provided
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


def test_policy_update_name_null_is_allowed_by_schema() -> None:
    """The schema allows null; the router rejects it with 422."""
    p = PolicyUpdate(name=None)
    assert p.name is None


# ---------------------------------------------------------------------------
# RuleOverride schemas
# ---------------------------------------------------------------------------


def test_rule_override_create_valid() -> None:
    override = RuleOverrideCreate(
        rule_id=942100,
        action=RuleAction.disable,
        comment=None,
    )
    assert override.rule_id == 942100
    assert override.comment is None


def test_rule_override_create_rule_id_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        RuleOverrideCreate(rule_id=0, action=RuleAction.disable)


def test_rule_override_update_valid() -> None:
    override = RuleOverrideUpdate(
        rule_id=941100,
        action=RuleAction.enable,
        comment=None,
    )
    assert override.rule_id == 941100
    assert override.action == RuleAction.enable


def test_rule_override_update_rule_id_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        RuleOverrideUpdate(rule_id=-1)


# ---------------------------------------------------------------------------
# VHostCreate
# ---------------------------------------------------------------------------


def test_vhost_create_valid() -> None:
    v = VHostCreate(domain="example.com", backend_url="http://localhost:8080")
    assert v.domain == "example.com"
    assert v.backend_url == "http://localhost:8080"


def test_vhost_create_domain_with_http_invalid() -> None:
    """The domain should not include a protocol."""
    with pytest.raises(ValidationError, match="should not include protocol"):
        VHostCreate(domain="http://example.com", backend_url="http://localhost:8080")


def test_vhost_create_domain_with_https_invalid() -> None:
    with pytest.raises(ValidationError, match="should not include protocol"):
        VHostCreate(domain="https://example.com", backend_url="http://localhost:8080")


def test_vhost_create_domain_lowercased() -> None:
    """The domain is normalized to lowercase."""
    v = VHostCreate(domain="EXAMPLE.COM", backend_url="http://localhost:8080")
    assert v.domain == "example.com"


def test_vhost_create_domain_stripped() -> None:
    """Whitespace around the domain is stripped before validation."""
    v = VHostCreate(domain="  example.com  ", backend_url="http://localhost:8080")
    assert v.domain == "example.com"


def test_vhost_create_backend_url_without_protocol_invalid() -> None:
    """A backend URL without a protocol is invalid."""
    with pytest.raises(ValidationError, match="must start with http"):
        VHostCreate(domain="example.com", backend_url="localhost:8080")


def test_vhost_create_backend_url_https_valid() -> None:
    v = VHostCreate(domain="example.com", backend_url="https://backend.internal:443")
    assert v.backend_url == "https://backend.internal:443"


def test_vhost_create_backend_url_stripped() -> None:
    """Whitespace around the backend URL is stripped."""
    v = VHostCreate(domain="example.com", backend_url="  http://localhost:8080  ")
    assert v.backend_url == "http://localhost:8080"
