"""Unit tests for the vhost service.

These tests use a real SQLAlchemy session with in-memory SQLite.
That keeps the tests focused on service logic and ORM behavior.
"""

import pytest
from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.models.user import User
from app.models.vhost import VHost
from app.services.vhost_service import (
    VHostDomainAlreadyExistsError,
    VHostFieldCannotBeNullError,
    VHostNotFoundError,
    VHostPolicyNotFoundError,
    VHostService,
)


def _create_policy_for_test(
    db: Session,
    *,
    name: str = "Default Policy",
    created_by: int | None = None,
) -> Policy:
    policy = Policy(
        name=name,
        description="Policy for vhost service tests",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
        created_by=created_by,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def test_create_vhost_persists_values_and_created_by(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)

    vhost = service.create_vhost(
        domain="app.example.com",
        backend_url="http://localhost:3000",
        description="Main app",
        ssl_enabled=True,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    assert vhost.id > 0
    assert vhost.domain == "app.example.com"
    assert vhost.backend_url == "http://localhost:3000"
    assert vhost.description == "Main app"
    assert vhost.ssl_enabled is True
    assert vhost.is_active is True
    assert vhost.policy_id is None
    assert vhost.created_by == admin_user.id


def test_create_vhost_with_existing_policy_succeeds(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)

    vhost = service.create_vhost(
        domain="policy.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=policy.id,
        created_by=admin_user.id,
    )

    assert vhost.policy_id == policy.id


def test_create_vhost_with_missing_policy_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)

    with pytest.raises(VHostPolicyNotFoundError):
        service.create_vhost(
            domain="missing-policy.example.com",
            backend_url="http://localhost:8080",
            description=None,
            ssl_enabled=False,
            is_active=True,
            policy_id=99999,
            created_by=admin_user.id,
        )


def test_create_vhost_duplicate_domain_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    service.create_vhost(
        domain="dup.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    with pytest.raises(VHostDomainAlreadyExistsError):
        service.create_vhost(
            domain="dup.example.com",
            backend_url="http://localhost:9090",
            description=None,
            ssl_enabled=False,
            is_active=True,
            policy_id=None,
            created_by=admin_user.id,
        )


def test_list_vhosts_returns_items_sorted_by_id(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    first = service.create_vhost(
        domain="a.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )
    second = service.create_vhost(
        domain="b.example.com",
        backend_url="http://localhost:8081",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    vhosts = service.list_vhosts()

    assert [vhost.id for vhost in vhosts] == [first.id, second.id]
    assert [vhost.domain for vhost in vhosts] == ["a.example.com", "b.example.com"]


def test_get_vhost_returns_existing_vhost(db: Session, admin_user: User) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, name="Nested Policy", created_by=admin_user.id)
    created = service.create_vhost(
        domain="detail.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=policy.id,
        created_by=admin_user.id,
    )

    vhost = service.get_vhost(created.id)

    assert vhost.id == created.id
    assert vhost.domain == "detail.example.com"
    assert vhost.policy is not None
    assert vhost.policy.id == policy.id


def test_get_vhost_missing_raises_not_found(db: Session) -> None:
    service = VHostService(db)

    with pytest.raises(VHostNotFoundError):
        service.get_vhost(99999)


def test_update_vhost_partial_update_changes_only_selected_fields(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    created = service.create_vhost(
        domain="patch.example.com",
        backend_url="http://localhost:8080",
        description="Before",
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    updated = service.update_vhost(
        created.id,
        {"backend_url": "https://backend.internal:443", "ssl_enabled": True},
    )

    assert updated.domain == "patch.example.com"
    assert updated.description == "Before"
    assert updated.backend_url == "https://backend.internal:443"
    assert updated.ssl_enabled is True
    assert updated.is_active is True


def test_update_vhost_null_for_non_nullable_field_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    created = service.create_vhost(
        domain="null.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    with pytest.raises(
        VHostFieldCannotBeNullError,
        match="Field 'domain' cannot be null",
    ):
        service.update_vhost(created.id, {"domain": None})


def test_update_vhost_with_missing_policy_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    created = service.create_vhost(
        domain="missing-patch.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    with pytest.raises(VHostPolicyNotFoundError):
        service.update_vhost(created.id, {"policy_id": 99999})


def test_update_vhost_duplicate_domain_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    service.create_vhost(
        domain="alpha.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )
    second = service.create_vhost(
        domain="beta.example.com",
        backend_url="http://localhost:8081",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    with pytest.raises(VHostDomainAlreadyExistsError):
        service.update_vhost(second.id, {"domain": "alpha.example.com"})


def test_delete_vhost_removes_existing_vhost(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    created = service.create_vhost(
        domain="delete.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    service.delete_vhost(created.id)

    assert db.get(VHost, created.id) is None


def test_delete_vhost_missing_raises_not_found(db: Session) -> None:
    service = VHostService(db)

    with pytest.raises(VHostNotFoundError):
        service.delete_vhost(99999)
