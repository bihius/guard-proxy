from datetime import datetime

from sqlalchemy.orm import Session

from app.models.runtime_operation import (
    RuntimeOperation,
    RuntimeOperationStatus,
    RuntimeOperationType,
)
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


def test_deployment_state_stays_never_deployed_with_only_failed_reloads(
    db: Session,
) -> None:
    _add_operation(
        db,
        operation_type=RuntimeOperationType.reload,
        status=RuntimeOperationStatus.failed,
        created_at=datetime(2026, 5, 16, 19, 0, 0),
    )
    service = RuntimeStatusService(db)

    status = service.get_runtime_status()

    assert status.deployment_state == "never_deployed"
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


def test_checksum_is_stable_for_same_generated_content() -> None:
    checksum_a = RuntimeStatusService._calculate_checksum("haproxy", "crs", "rules")
    checksum_b = RuntimeStatusService._calculate_checksum("haproxy", "crs", "rules")

    assert checksum_a == checksum_b
    assert len(checksum_a) == 64


def test_checksum_changes_when_generated_content_changes() -> None:
    checksum_a = RuntimeStatusService._calculate_checksum("haproxy", "crs", "rules")
    checksum_b = RuntimeStatusService._calculate_checksum("haproxy-changed", "crs", "rules")

    assert checksum_a != checksum_b
