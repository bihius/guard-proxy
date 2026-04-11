"""Unit tests for log router helper functions."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.log import Log, LogAction, LogSeverity
from app.routers.logs import _persist_log_event


def _make_log(producer_event_id: str | None = "event-123") -> Log:
    return Log(
        producer_event_id=producer_event_id,
        event_at=datetime(2026, 4, 11, 10, 30, 0),
        vhost="app.example.com",
        action=LogAction.deny,
        source_ip="203.0.113.10",
        method="POST",
        request_uri="/login",
        status_code=403,
        rule_id=942100,
        rule_message="SQL injection attack detected",
        anomaly_score=15,
        paranoia_level=2,
        severity=LogSeverity.error,
        message="Blocked by Coraza",
        raw_context={"engine": "coraza"},
    )


def test_persist_log_event_returns_existing_on_integrity_error_retry() -> None:
    db = MagicMock()
    existing = _make_log("event-123")
    db.commit.side_effect = IntegrityError("", {}, Exception())
    db.query.return_value.filter.return_value.one_or_none.return_value = existing

    persisted, created = _persist_log_event(
        db=db,
        log=_make_log("event-123"),
        producer_event_id="event-123",
    )

    assert persisted is existing
    assert created is False
    db.add.assert_called_once()
    db.rollback.assert_called_once()


def test_persist_log_event_reraises_integrity_error_without_existing_row() -> None:
    db = MagicMock()
    db.commit.side_effect = IntegrityError("", {}, Exception())
    db.query.return_value.filter.return_value.one_or_none.return_value = None

    with pytest.raises(IntegrityError):
        _persist_log_event(
            db=db,
            log=_make_log("event-123"),
            producer_event_id="event-123",
        )
