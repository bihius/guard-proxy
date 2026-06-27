from datetime import datetime

from sqlalchemy.orm import Session

from app.models.policy import Policy, PolicyEnforcementMode
from app.models.rule_override import RuleAction, RuleOverride
from app.models.runtime_operation import (
    RuntimeOperation,
    RuntimeOperationStatus,
    RuntimeOperationType,
)
from app.models.vhost import VHost
from app.services.config_generator import generate
from app.services.runtime_status_service import RuntimeStatusService


def _add_operation(
    db: Session,
    *,
    operation_type: RuntimeOperationType,
    status: RuntimeOperationStatus,
    created_at: datetime,
) -> RuntimeOperation:
    operation = RuntimeOperation(
        operation_type=operation_type,
        status=status,
        created_at=created_at,
    )
    db.add(operation)
    db.commit()
    db.refresh(operation)
    return operation


def test_deployment_state_is_never_deployed_without_reload_records(db: Session) -> None:
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.deployment_state == "never_deployed"
    assert status.latest_reload is None


def test_deployment_state_is_deployed_when_latest_reload_succeeded(db: Session) -> None:
    _add_operation(
        db,
        operation_type=RuntimeOperationType.reload,
        status=RuntimeOperationStatus.success,
        created_at=datetime(2026, 5, 16, 19, 0, 0),
    )
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.deployment_state == "deployed"
    assert status.latest_reload is not None
    assert status.latest_reload.status == RuntimeOperationStatus.success


def test_deployment_state_is_failed_with_only_failed_reloads_and_no_prior_success(
    db: Session,
) -> None:
    """A failed reload with no prior successful reload is 'failed', not 'never_deployed'.
    The API was called and a reload was attempted; that attempt failed."""
    _add_operation(
        db,
        operation_type=RuntimeOperationType.reload,
        status=RuntimeOperationStatus.failed,
        created_at=datetime(2026, 5, 16, 19, 0, 0),
    )
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.deployment_state == "failed"
    assert status.latest_reload is not None
    assert status.latest_reload.status == RuntimeOperationStatus.failed


def test_deployment_state_is_failed_when_latest_reload_failed_after_success(
    db: Session,
) -> None:
    _add_operation(
        db,
        operation_type=RuntimeOperationType.reload,
        status=RuntimeOperationStatus.success,
        created_at=datetime(2026, 5, 16, 19, 0, 0),
    )
    _add_operation(
        db,
        operation_type=RuntimeOperationType.reload,
        status=RuntimeOperationStatus.failed,
        created_at=datetime(2026, 5, 16, 19, 5, 0),
    )
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.deployment_state == "failed"
    assert status.latest_reload is not None
    assert status.latest_reload.status == RuntimeOperationStatus.failed


def _add_policy(
    db: Session,
    *,
    name: str,
    is_active: bool = True,
    enforcement_mode: PolicyEnforcementMode = PolicyEnforcementMode.block,
) -> Policy:
    policy = Policy(
        name=name,
        paranoia_level=1,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=4,
        enforcement_mode=enforcement_mode,
        is_active=is_active,
    )
    db.add(policy)
    db.flush()
    return policy


def _add_vhost(
    db: Session,
    *,
    domain: str,
    backend_url: str,
    policy_id: int | None = None,
) -> VHost:
    vhost = VHost(
        domain=domain,
        backend_url=backend_url,
        is_active=True,
        ssl_enabled=False,
        policy_id=policy_id,
    )
    db.add(vhost)
    db.flush()
    return vhost


def test_generated_config_supports_multiple_active_vhosts(
    db: Session,
) -> None:
    _add_vhost(
        db,
        domain="app.example.com",
        backend_url="http://app-backend:8000",
    )
    _add_vhost(
        db,
        domain="api.example.com",
        backend_url="http://api-backend:8000",
    )
    db.commit()
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.generated_config.can_generate is True
    assert status.generated_config.checksum is not None
    assert status.generated_config.generated_at is not None
    assert status.generated_config.error is None


def test_haproxy_context_uses_vhost_id_identifiers_for_colliding_domains(
    db: Session,
) -> None:
    first = _add_vhost(
        db,
        domain="foo-bar.com",
        backend_url="http://foo-backend:8000",
    )
    second = _add_vhost(
        db,
        domain="foo.bar.com",
        backend_url="http://bar-backend:8000",
    )

    generated = generate(vhosts=[first, second], policies=[], rule_overrides=[])
    rendered = generated.haproxy_cfg

    assert f"acl host_vhost_{first.id} hdr(host),field(1,:) -i foo-bar.com" in rendered
    assert f"acl host_vhost_{second.id} hdr(host),field(1,:) -i foo.bar.com" in rendered
    assert f"backend be_vhost_{first.id}" in rendered
    assert f"backend be_vhost_{second.id}" in rendered
    assert "host_foo_bar_com" not in rendered


def test_generated_config_does_not_dirty_policy_relationships(
    db: Session,
) -> None:
    policy = _add_policy(db, name="Pure generator")
    _add_vhost(
        db,
        domain="app.example.com",
        backend_url="http://app-backend:8000",
        policy_id=policy.id,
    )
    db.add(
        RuleOverride(
            policy_id=policy.id,
            rule_id=942100,
            action=RuleAction.disable,
        )
    )
    db.commit()
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.generated_config.can_generate is True
    assert not db.dirty


def test_generated_config_rejects_mixed_active_policies(db: Session) -> None:
    first_policy = _add_policy(db, name="Strict")
    second_policy = _add_policy(db, name="Monitor")
    _add_vhost(
        db,
        domain="app.example.com",
        backend_url="http://app-backend:8000",
        policy_id=first_policy.id,
    )
    _add_vhost(
        db,
        domain="api.example.com",
        backend_url="http://api-backend:8000",
        policy_id=second_policy.id,
    )
    db.commit()
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.generated_config.can_generate is False
    assert status.generated_config.error is not None
    assert "one active CRS policy" in status.generated_config.error


def test_generated_config_rejects_inactive_assigned_policy(db: Session) -> None:
    policy = _add_policy(db, name="Inactive", is_active=False)
    _add_vhost(
        db,
        domain="app.example.com",
        backend_url="http://app-backend:8000",
        policy_id=policy.id,
    )
    db.commit()
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.generated_config.can_generate is False
    assert status.generated_config.error is not None
    assert "inactive policy" in status.generated_config.error


def test_active_policy_selection_rejects_missing_policy() -> None:
    vhost = VHost(
        id=1,
        domain="app.example.com",
        backend_url="http://app-backend:8000",
        is_active=True,
        ssl_enabled=False,
        policy_id=999,
    )

    try:
        generate(vhosts=[vhost], policies=[], rule_overrides=[])
    except ValueError as error:
        assert "missing policy 999" in str(error)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected missing policy to fail generation")


def test_checksum_is_stable_for_same_generated_content() -> None:
    checksum_a = RuntimeStatusService._calculate_checksum("haproxy", "crs", "rules")
    checksum_b = RuntimeStatusService._calculate_checksum("haproxy", "crs", "rules")

    assert checksum_a == checksum_b
    assert len(checksum_a) == 64


def test_checksum_changes_when_generated_content_changes() -> None:
    checksum_a = RuntimeStatusService._calculate_checksum("haproxy", "crs", "rules")
    checksum_b = RuntimeStatusService._calculate_checksum(
        "haproxy-changed",
        "crs",
        "rules",
    )

    assert checksum_a != checksum_b


# ---------------------------------------------------------------------------
# MED M6 — policy-less vhosts must not cause "policy id 0" error
# ---------------------------------------------------------------------------


def test_generated_config_allows_policy_less_vhost_alongside_policy_bound(
    db: Session,
) -> None:
    """A mix of policy-less and policy-bound active vhosts should not raise.
    Previously this caused 'found effective policies: 0, <id>' due to sentinel 0."""
    policy = _add_policy(db, name="Production")
    _add_vhost(
        db,
        domain="app.example.com",
        backend_url="http://app-backend:8000",
        policy_id=policy.id,
    )
    _add_vhost(
        db,
        domain="api.example.com",
        backend_url="http://api-backend:8000",
        policy_id=None,  # policy-less
    )
    db.commit()
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.generated_config.can_generate is True
    assert status.generated_config.error is None
    # The policy-less vhost should be reported in the warning field
    assert status.generated_config.unbound_vhost_domains == ["api.example.com"]


def test_generated_config_reports_unbound_vhost_domains(db: Session) -> None:
    """All policy-less active vhosts are listed in unbound_vhost_domains."""
    _add_vhost(
        db,
        domain="a.example.com",
        backend_url="http://a-backend:8000",
        policy_id=None,
    )
    _add_vhost(
        db,
        domain="b.example.com",
        backend_url="http://b-backend:8000",
        policy_id=None,
    )
    db.commit()
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.generated_config.can_generate is True
    assert status.generated_config.unbound_vhost_domains is not None
    assert set(status.generated_config.unbound_vhost_domains) == {
        "a.example.com",
        "b.example.com",
    }


def test_generated_config_unbound_vhost_domains_is_none_when_all_bound(
    db: Session,
) -> None:
    policy = _add_policy(db, name="Strict")
    _add_vhost(
        db,
        domain="app.example.com",
        backend_url="http://app-backend:8000",
        policy_id=policy.id,
    )
    db.commit()
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.generated_config.can_generate is True
    assert status.generated_config.unbound_vhost_domains is None
