"""Unit tests for the vhost service.

These tests use a real SQLAlchemy session with in-memory SQLite.
That keeps the tests focused on service logic and ORM behavior.
"""

import pytest
from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.models.policy_binding import PolicyBinding
from app.models.user import User
from app.models.vhost import VHost
from app.services.vhost_service import (
    PolicyBindingAlreadyExistsError,
    PolicyBindingDefaultManagedByVHostError,
    PolicyBindingInvalidPathPrefixError,
    PolicyBindingInvalidPriorityError,
    PolicyBindingNotFoundError,
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
    assert len(vhost.policy_bindings) == 1
    assert vhost.policy_bindings[0].policy_id == policy.id
    assert vhost.policy_bindings[0].path_prefix == "/"
    assert vhost.policy_bindings[0].priority == 0


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

    vhosts, total = service.list_vhosts()

    assert total == 2
    assert [vhost.id for vhost in vhosts] == [first.id, second.id]
    assert [vhost.domain for vhost in vhosts] == ["a.example.com", "b.example.com"]


def test_list_vhosts_paginates_results(db: Session, admin_user: User) -> None:
    service = VHostService(db)
    for index in range(3):
        service.create_vhost(
            domain=f"host{index}.example.com",
            backend_url="http://localhost:8080",
            description=None,
            ssl_enabled=False,
            is_active=True,
            policy_id=None,
            created_by=admin_user.id,
        )

    first_page, total = service.list_vhosts(page=1, per_page=2)
    second_page, _ = service.list_vhosts(page=2, per_page=2)

    assert total == 3
    assert [vhost.domain for vhost in first_page] == [
        "host0.example.com",
        "host1.example.com",
    ]
    assert [vhost.domain for vhost in second_page] == ["host2.example.com"]


def test_list_vhosts_filters_by_domain_substring(db: Session, admin_user: User) -> None:
    service = VHostService(db)
    service.create_vhost(
        domain="app.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )
    service.create_vhost(
        domain="api.other.com",
        backend_url="http://localhost:8081",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    vhosts, total = service.list_vhosts(q="example")

    assert total == 1
    assert [vhost.domain for vhost in vhosts] == ["app.example.com"]


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


def test_update_vhost_policy_id_syncs_default_binding(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    first_policy = _create_policy_for_test(db, name="First", created_by=admin_user.id)
    second_policy = _create_policy_for_test(db, name="Second", created_by=admin_user.id)
    created = service.create_vhost(
        domain="sync-policy.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=first_policy.id,
        created_by=admin_user.id,
    )

    updated = service.update_vhost(created.id, {"policy_id": second_policy.id})

    bindings = service.list_policy_bindings(updated.id)
    assert updated.policy_id == second_policy.id
    assert len(bindings) == 1
    assert bindings[0].policy_id == second_policy.id
    assert bindings[0].path_prefix == "/"


def test_update_vhost_policy_id_null_removes_default_binding(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)
    created = service.create_vhost(
        domain="clear-policy.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=policy.id,
        created_by=admin_user.id,
    )

    updated = service.update_vhost(created.id, {"policy_id": None})

    assert updated.policy_id is None
    assert service.list_policy_bindings(updated.id) == []


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


def test_create_policy_binding_persists_values(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)
    vhost = service.create_vhost(
        domain="binding.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    binding = service.create_policy_binding(
        vhost.id,
        policy_id=policy.id,
        path_prefix="/api",
        priority=10,
        comment="API policy",
    )

    assert binding.id > 0
    assert binding.vhost_id == vhost.id
    assert binding.policy_id == policy.id
    assert binding.path_prefix == "/api"
    assert binding.priority == 10
    assert binding.comment == "API policy"


def test_list_policy_bindings_returns_priority_order(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)
    vhost = service.create_vhost(
        domain="ordered-bindings.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )
    second = service.create_policy_binding(
        vhost.id,
        policy_id=policy.id,
        path_prefix="/api",
        priority=20,
        comment=None,
    )
    first = service.create_policy_binding(
        vhost.id,
        policy_id=policy.id,
        path_prefix="/admin",
        priority=10,
        comment=None,
    )

    bindings = service.list_policy_bindings(vhost.id)

    assert [binding.id for binding in bindings] == [first.id, second.id]


def test_create_policy_binding_duplicate_path_priority_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)
    vhost = service.create_vhost(
        domain="duplicate-binding.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )
    service.create_policy_binding(
        vhost.id,
        policy_id=policy.id,
        path_prefix="/api",
        priority=1,
        comment=None,
    )

    with pytest.raises(PolicyBindingAlreadyExistsError):
        service.create_policy_binding(
            vhost.id,
            policy_id=policy.id,
            path_prefix="/api",
            priority=1,
            comment=None,
        )


def test_create_policy_binding_rejects_default_root_binding(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)
    vhost = service.create_vhost(
        domain="direct-root-binding.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    with pytest.raises(PolicyBindingDefaultManagedByVHostError):
        service.create_policy_binding(
            vhost.id,
            policy_id=policy.id,
            path_prefix="/",
            priority=0,
            comment=None,
        )


def test_create_policy_binding_invalid_path_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)
    vhost = service.create_vhost(
        domain="invalid-path-binding.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    with pytest.raises(PolicyBindingInvalidPathPrefixError):
        service.create_policy_binding(
            vhost.id,
            policy_id=policy.id,
            path_prefix="api",
            priority=1,
            comment=None,
        )


def test_create_policy_binding_invalid_priority_raises_error(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)
    vhost = service.create_vhost(
        domain="invalid-priority-binding.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    with pytest.raises(PolicyBindingInvalidPriorityError):
        service.create_policy_binding(
            vhost.id,
            policy_id=policy.id,
            path_prefix="/api",
            priority=-1,
            comment=None,
        )


def test_delete_policy_binding_removes_existing_binding(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)
    vhost = service.create_vhost(
        domain="delete-binding.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )
    binding = service.create_policy_binding(
        vhost.id,
        policy_id=policy.id,
        path_prefix="/api",
        priority=1,
        comment=None,
    )

    service.delete_policy_binding(vhost.id, binding.id)

    assert db.get(PolicyBinding, binding.id) is None


def test_delete_policy_binding_rejects_default_root_binding(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    policy = _create_policy_for_test(db, created_by=admin_user.id)
    vhost = service.create_vhost(
        domain="delete-root-binding.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=policy.id,
        created_by=admin_user.id,
    )
    binding = service.list_policy_bindings(vhost.id)[0]

    with pytest.raises(PolicyBindingDefaultManagedByVHostError):
        service.delete_policy_binding(vhost.id, binding.id)

    refreshed = service.get_vhost(vhost.id)
    assert refreshed.policy_id == policy.id
    assert len(service.list_policy_bindings(vhost.id)) == 1


def test_delete_policy_binding_missing_raises_not_found(
    db: Session,
    admin_user: User,
) -> None:
    service = VHostService(db)
    vhost = service.create_vhost(
        domain="missing-binding.example.com",
        backend_url="http://localhost:8080",
        description=None,
        ssl_enabled=False,
        is_active=True,
        policy_id=None,
        created_by=admin_user.id,
    )

    with pytest.raises(PolicyBindingNotFoundError):
        service.delete_policy_binding(vhost.id, 99999)
