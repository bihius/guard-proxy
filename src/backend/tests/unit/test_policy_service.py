"""Unit tests for the policy service.

These tests use a real SQLAlchemy session with in-memory SQLite.
That keeps the tests simple for a junior developer:
- no HTTP layer
- no FastAPI router
- only service logic plus database behavior
"""

import os

import pytest
from sqlalchemy.orm import Session

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-onlyx")

from app.models.policy import Policy  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.policy_service import (  # noqa: E402
    PolicyDisallowedFieldError,
    PolicyFieldCannotBeNullError,
    PolicyNameAlreadyExistsError,
    PolicyNotFoundError,
    PolicyService,
)


def test_create_policy_persists_values_and_created_by(
    db: Session,
    admin_user: User,
) -> None:
    service = PolicyService(db)

    policy = service.create_policy(
        name="Strict",
        description="High protection",
        paranoia_level=4,
        anomaly_threshold=7,
        created_by=admin_user.id,
    )

    assert policy.id > 0
    assert policy.name == "Strict"
    assert policy.description == "High protection"
    assert policy.paranoia_level == 4
    assert policy.anomaly_threshold == 7
    assert policy.is_active is True
    assert policy.created_by == admin_user.id


def test_create_policy_duplicate_name_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = PolicyService(db)
    service.create_policy(
        name="Duplicate",
        description=None,
        paranoia_level=2,
        anomaly_threshold=5,
        created_by=admin_user.id,
    )

    with pytest.raises(PolicyNameAlreadyExistsError):
        service.create_policy(
            name="Duplicate",
            description=None,
            paranoia_level=1,
            anomaly_threshold=3,
            created_by=admin_user.id,
        )


def test_list_policies_returns_items_sorted_by_id(
    db: Session,
    admin_user: User,
) -> None:
    service = PolicyService(db)
    first = service.create_policy(
        name="Alpha",
        description=None,
        paranoia_level=1,
        anomaly_threshold=5,
        created_by=admin_user.id,
    )
    second = service.create_policy(
        name="Beta",
        description=None,
        paranoia_level=2,
        anomaly_threshold=6,
        created_by=admin_user.id,
    )

    policies = service.list_policies()

    assert [policy.id for policy in policies] == [first.id, second.id]
    assert [policy.name for policy in policies] == ["Alpha", "Beta"]


def test_get_policy_returns_existing_policy(db: Session, admin_user: User) -> None:
    service = PolicyService(db)
    created = service.create_policy(
        name="Detail",
        description="Read me",
        paranoia_level=2,
        anomaly_threshold=5,
        created_by=admin_user.id,
    )

    policy = service.get_policy(created.id)

    assert policy.id == created.id
    assert policy.name == "Detail"
    assert policy.rule_overrides == []


def test_get_policy_missing_raises_not_found(db: Session) -> None:
    service = PolicyService(db)

    with pytest.raises(PolicyNotFoundError):
        service.get_policy(99999)


def test_update_policy_partial_update_changes_only_selected_fields(
    db: Session,
    admin_user: User,
) -> None:
    service = PolicyService(db)
    created = service.create_policy(
        name="Patch me",
        description="Before",
        paranoia_level=2,
        anomaly_threshold=5,
        created_by=admin_user.id,
    )

    updated = service.update_policy(
        created.id,
        {"paranoia_level": 3, "is_active": False},
    )

    assert updated.name == "Patch me"
    assert updated.description == "Before"
    assert updated.paranoia_level == 3
    assert updated.anomaly_threshold == 5
    assert updated.is_active is False


def test_update_policy_null_for_non_nullable_field_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = PolicyService(db)
    created = service.create_policy(
        name="Null check",
        description=None,
        paranoia_level=2,
        anomaly_threshold=5,
        created_by=admin_user.id,
    )

    with pytest.raises(
        PolicyFieldCannotBeNullError,
        match="Field 'name' cannot be null",
    ):
        service.update_policy(created.id, {"name": None})


def test_update_policy_duplicate_name_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = PolicyService(db)
    service.create_policy(
        name="Alpha",
        description=None,
        paranoia_level=2,
        anomaly_threshold=5,
        created_by=admin_user.id,
    )
    second = service.create_policy(
        name="Beta",
        description=None,
        paranoia_level=2,
        anomaly_threshold=5,
        created_by=admin_user.id,
    )

    with pytest.raises(PolicyNameAlreadyExistsError):
        service.update_policy(second.id, {"name": "Alpha"})


def test_delete_policy_removes_existing_policy(db: Session, admin_user: User) -> None:
    service = PolicyService(db)
    created = service.create_policy(
        name="Delete me",
        description=None,
        paranoia_level=2,
        anomaly_threshold=5,
        created_by=admin_user.id,
    )

    service.delete_policy(created.id)

    assert db.get(Policy, created.id) is None


def test_delete_policy_missing_raises_not_found(db: Session) -> None:
    service = PolicyService(db)

    with pytest.raises(PolicyNotFoundError):
        service.delete_policy(99999)


def test_update_policy_disallowed_field_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = PolicyService(db)
    created = service.create_policy(
        name="Allowlist check",
        description=None,
        paranoia_level=2,
        anomaly_threshold=5,
        created_by=admin_user.id,
    )

    with pytest.raises(
        PolicyDisallowedFieldError,
        match="Field 'created_by' cannot be patched",
    ):
        service.update_policy(created.id, {"created_by": 999})
