"""Unit tests for the log retention cleanup function."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.log import Log, LogAction, LogSeverity
from app.services.log_retention import purge_logs_older_than


def _make_log(event_at: datetime) -> Log:
    return Log(
        event_at=event_at,
        vhost="app.example.com",
        action=LogAction.allow,
        source_ip="203.0.113.10",
        method="GET",
        request_uri="/health",
        status_code=200,
        severity=LogSeverity.info,
    )


def test_purge_logs_older_than_removes_only_old_rows(db: Session) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    old_log = _make_log(now - timedelta(days=31))
    recent_log = _make_log(now - timedelta(days=1))
    db.add_all([old_log, recent_log])
    db.commit()

    deleted = purge_logs_older_than(db, retention_days=30)

    assert deleted == 1
    remaining = db.query(Log).all()
    assert len(remaining) == 1
    assert remaining[0].id == recent_log.id


def test_purge_logs_older_than_keeps_row_within_threshold(db: Session) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    boundary_log = _make_log(now - timedelta(days=29, hours=23, minutes=59))
    db.add(boundary_log)
    db.commit()

    deleted = purge_logs_older_than(db, retention_days=30)

    assert deleted == 0
    assert db.query(Log).count() == 1
