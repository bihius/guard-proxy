from __future__ import annotations

from sqlalchemy.orm import Session

from app.main import _reconcile_runtime_operation_checksum
from app.models.runtime_operation import (
    RuntimeOperation,
    RuntimeOperationStatus,
    RuntimeOperationType,
)


def test_reconcile_inserts_reload_row_when_none_exists(db: Session) -> None:
    _reconcile_runtime_operation_checksum(db, "checksum-a")

    rows = db.query(RuntimeOperation).all()
    assert len(rows) == 1
    assert rows[0].operation_type == RuntimeOperationType.reload
    assert rows[0].status == RuntimeOperationStatus.success
    assert rows[0].config_checksum == "checksum-a"


def test_reconcile_skips_insert_when_checksum_matches_latest_reload(
    db: Session,
) -> None:
    db.add(
        RuntimeOperation(
            operation_type=RuntimeOperationType.reload,
            status=RuntimeOperationStatus.success,
            config_checksum="checksum-a",
        )
    )
    db.commit()

    _reconcile_runtime_operation_checksum(db, "checksum-a")

    rows = db.query(RuntimeOperation).all()
    assert len(rows) == 1


def test_reconcile_inserts_new_row_when_checksum_diverges(db: Session) -> None:
    db.add(
        RuntimeOperation(
            operation_type=RuntimeOperationType.reload,
            status=RuntimeOperationStatus.success,
            config_checksum="checksum-a",
        )
    )
    db.commit()

    _reconcile_runtime_operation_checksum(db, "checksum-b")

    rows = (
        db.query(RuntimeOperation)
        .order_by(RuntimeOperation.created_at.asc(), RuntimeOperation.id.asc())
        .all()
    )
    assert len(rows) == 2
    assert rows[0].config_checksum == "checksum-a"
    assert rows[1].config_checksum == "checksum-b"


def test_reconcile_skips_when_no_active_checksum(db: Session) -> None:
    _reconcile_runtime_operation_checksum(db, None)

    rows = db.query(RuntimeOperation).all()
    assert len(rows) == 0
