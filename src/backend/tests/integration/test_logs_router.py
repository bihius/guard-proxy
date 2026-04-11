"""Integration tests for log ingestion and log listing APIs."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.log import Log, LogAction, LogSeverity


def _create_log(
    db: Session,
    *,
    event_at: datetime,
    vhost: str = "app.example.com",
    action: LogAction = LogAction.allow,
    source_ip: str = "203.0.113.10",
    method: str = "GET",
    request_uri: str = "/health",
    status_code: int | None = 200,
    rule_id: int | None = None,
    rule_message: str | None = None,
    anomaly_score: int | None = None,
    paranoia_level: int | None = None,
    severity: LogSeverity = LogSeverity.info,
    message: str | None = None,
    raw_context: dict[str, object] | None = None,
    producer_event_id: str | None = None,
) -> Log:
    """Persist a log event in the test database."""
    log = Log(
        producer_event_id=producer_event_id,
        event_at=event_at,
        vhost=vhost,
        action=action,
        source_ip=source_ip,
        method=method,
        request_uri=request_uri,
        status_code=status_code,
        rule_id=rule_id,
        rule_message=rule_message,
        anomaly_score=anomaly_score,
        paranoia_level=paranoia_level,
        severity=severity,
        message=message,
        raw_context=raw_context,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _ingest_payload(**overrides: object) -> dict[str, object]:
    """Return a valid ingest payload that tests can tweak."""
    payload: dict[str, object] = {
        "producer_event_id": "coraza-event-1",
        "event_at": "2026-04-11T10:30:00",
        "vhost": "app.example.com",
        "action": "deny",
        "source_ip": "203.0.113.10",
        "method": "post",
        "request_uri": "/login?next=%2Fadmin",
        "status_code": 403,
        "rule_id": 942100,
        "rule_message": "SQL injection attack detected",
        "anomaly_score": 15,
        "paranoia_level": 2,
        "severity": "error",
        "message": "Request blocked by Coraza",
        "raw_context": {"engine": "coraza", "phase": "request"},
    }
    payload.update(overrides)
    return payload


def test_list_logs_returns_paginated_results_for_admin(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """Admin can list rich log events and receives pagination metadata."""
    older = _create_log(
        db,
        event_at=datetime(2026, 3, 20, 10, 0, 0),
        action=LogAction.monitor,
        severity=LogSeverity.warning,
        message="Older event",
    )
    newer = _create_log(
        db,
        event_at=datetime(2026, 3, 21, 10, 0, 0),
        action=LogAction.deny,
        status_code=403,
        rule_id=949110,
        severity=LogSeverity.error,
        message="Newer event",
        raw_context={"engine": "coraza"},
    )

    resp = client.get("/logs", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert [item["id"] for item in body["items"]] == [newer.id, older.id]
    assert body["items"][0]["action"] == "deny"
    assert body["items"][0]["rule_id"] == 949110
    assert body["items"][0]["raw_context"] == {"engine": "coraza"}


def test_list_logs_viewer_has_read_access(
    client: TestClient,
    db: Session,
    viewer_token: dict[str, str],
) -> None:
    """Viewer still has read-only access to the log list."""
    _create_log(
        db,
        event_at=datetime(2026, 3, 21, 10, 0, 0),
        vhost="frontend.example.com",
        action=LogAction.allow,
        severity=LogSeverity.info,
        message="Rendered dashboard",
    )

    resp = client.get("/logs", headers=viewer_token)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_logs_requires_auth(client: TestClient) -> None:
    """Listing logs without auth should fail."""
    resp = client.get("/logs")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_list_logs_filters_by_vhost_action_and_severity(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """The API should apply multiple exact-match filters at once."""
    _create_log(
        db,
        event_at=datetime(2026, 3, 21, 8, 0, 0),
        vhost="api.example.com",
        action=LogAction.deny,
        severity=LogSeverity.error,
        message="Matched",
    )
    _create_log(
        db,
        event_at=datetime(2026, 3, 21, 9, 0, 0),
        vhost="api.example.com",
        action=LogAction.allow,
        severity=LogSeverity.error,
        message="Wrong action",
    )
    _create_log(
        db,
        event_at=datetime(2026, 3, 21, 10, 0, 0),
        vhost="www.example.com",
        action=LogAction.deny,
        severity=LogSeverity.error,
        message="Wrong vhost",
    )

    resp = client.get(
        "/logs",
        headers=admin_token,
        params={
            "vhost": "API.EXAMPLE.COM",
            "action": "deny",
            "severity": "error",
        },
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "Matched"


def test_list_logs_filters_by_date_range(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """Date filters should keep only events inside the selected range."""
    _create_log(
        db,
        event_at=datetime(2026, 3, 19, 23, 59, 59),
        message="Too early",
    )
    _create_log(
        db,
        event_at=datetime(2026, 3, 20, 12, 0, 0),
        message="In range",
    )
    _create_log(
        db,
        event_at=datetime(2026, 3, 22, 0, 0, 1),
        message="Too late",
    )

    resp = client.get(
        "/logs",
        headers=admin_token,
        params={
            "date_from": "2026-03-20T00:00:00",
            "date_to": "2026-03-22T00:00:00",
        },
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "In range"


def test_list_logs_filters_by_source_ip(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """The source IP filter should match a single address exactly."""
    _create_log(
        db,
        event_at=datetime(2026, 3, 21, 10, 0, 0),
        source_ip="198.51.100.8",
        message="Matched IP",
    )
    _create_log(
        db,
        event_at=datetime(2026, 3, 21, 11, 0, 0),
        source_ip="203.0.113.9",
        message="Wrong IP",
    )

    resp = client.get(
        "/logs",
        headers=admin_token,
        params={"source_ip": "198.51.100.8"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "Matched IP"


def test_list_logs_filters_by_method_status_code_and_rule_id(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """Method, status code, and rule id filters should all be usable."""
    _create_log(
        db,
        event_at=datetime(2026, 3, 21, 8, 0, 0),
        method="POST",
        status_code=403,
        rule_id=942100,
        message="Matched event",
    )
    _create_log(
        db,
        event_at=datetime(2026, 3, 21, 9, 0, 0),
        method="GET",
        status_code=403,
        rule_id=942100,
        message="Wrong method",
    )

    resp = client.get(
        "/logs",
        headers=admin_token,
        params={
            "method": "post",
            "status_code": 403,
            "rule_id": 942100,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "Matched event"


def test_list_logs_serializes_nullable_fields(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """Optional investigation fields should serialize as null when absent."""
    log = _create_log(
        db,
        event_at=datetime(2026, 3, 21, 8, 0, 0),
        status_code=None,
        rule_id=None,
        rule_message=None,
        anomaly_score=None,
        paranoia_level=None,
        message=None,
        raw_context=None,
    )

    resp = client.get("/logs", headers=admin_token)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["id"] == log.id
    assert body["items"][0]["status_code"] is None
    assert body["items"][0]["rule_id"] is None
    assert body["items"][0]["raw_context"] is None
    assert body["items"][0]["message"] is None


def test_list_logs_paginates_results(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """Pagination should return the requested slice of the ordered result set."""
    _create_log(db, event_at=datetime(2026, 3, 21, 8, 0, 0), message="First")
    second = _create_log(
        db,
        event_at=datetime(2026, 3, 21, 9, 0, 0),
        message="Second",
    )
    _create_log(db, event_at=datetime(2026, 3, 21, 10, 0, 0), message="Third")

    resp = client.get(
        "/logs",
        headers=admin_token,
        params={"page": 2, "page_size": 1},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == second.id


def test_list_logs_rejects_invalid_date_range(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """date_from later than date_to should be rejected explicitly."""
    resp = client.get(
        "/logs",
        headers=admin_token,
        params={
            "date_from": "2026-03-22T00:00:00",
            "date_to": "2026-03-20T00:00:00",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "date_from cannot be later than date_to"


def test_ingest_log_event_persists_valid_payload(
    client: TestClient,
    db: Session,
    log_ingest_headers: dict[str, str],
) -> None:
    """A valid ingest request should store the event in the database."""
    resp = client.post("/logs/ingest", json=_ingest_payload(), headers=log_ingest_headers)
    assert resp.status_code == 201

    body = resp.json()
    assert body["method"] == "POST"
    assert body["vhost"] == "app.example.com"
    assert body["producer_event_id"] == "coraza-event-1"

    persisted = db.query(Log).filter(Log.producer_event_id == "coraza-event-1").one()
    assert persisted.action == LogAction.deny
    assert persisted.method == "POST"
    assert persisted.raw_context == {"engine": "coraza", "phase": "request"}


def test_ingest_log_event_requires_secret(client: TestClient) -> None:
    """Missing shared secret should return 401."""
    resp = client.post("/logs/ingest", json=_ingest_payload())
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing ingest secret"


def test_ingest_log_event_rejects_invalid_secret(client: TestClient) -> None:
    """Wrong shared secret should return 403."""
    resp = client.post(
        "/logs/ingest",
        json=_ingest_payload(),
        headers={"X-Guard-Proxy-Ingest-Secret": "wrong-secret"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Invalid ingest secret"


def test_ingest_log_event_rejects_invalid_payload(
    client: TestClient,
    log_ingest_headers: dict[str, str],
) -> None:
    """Malformed ingest payloads should fail with 422 validation errors."""
    resp = client.post(
        "/logs/ingest",
        json=_ingest_payload(source_ip="not-an-ip", severity="fatal"),
        headers=log_ingest_headers,
    )
    assert resp.status_code == 422


def test_ingest_log_event_allows_optional_fields_to_be_omitted(
    client: TestClient,
    log_ingest_headers: dict[str, str],
) -> None:
    """Optional investigation fields should not be required on ingest."""
    resp = client.post(
        "/logs/ingest",
        json=_ingest_payload(
            producer_event_id="coraza-event-2",
            status_code=None,
            rule_id=None,
            rule_message=None,
            anomaly_score=None,
            paranoia_level=None,
            message=None,
            raw_context=None,
        ),
        headers=log_ingest_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status_code"] is None
    assert body["rule_id"] is None
    assert body["raw_context"] is None


def test_ingest_log_event_is_idempotent_when_producer_event_id_retries(
    client: TestClient,
    db: Session,
    log_ingest_headers: dict[str, str],
) -> None:
    """Retrying the same producer event id should return the existing record."""
    first = client.post("/logs/ingest", json=_ingest_payload(), headers=log_ingest_headers)
    second = client.post(
        "/logs/ingest",
        json=_ingest_payload(message="Changed body should still dedupe"),
        headers=log_ingest_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert db.query(Log).count() == 1


def test_ingest_then_list_logs_returns_persisted_event(
    client: TestClient,
    admin_token: dict[str, str],
    log_ingest_headers: dict[str, str],
) -> None:
    """An ingested event should be visible through the read API immediately."""
    ingest = client.post(
        "/logs/ingest",
        json=_ingest_payload(producer_event_id="coraza-event-3"),
        headers=log_ingest_headers,
    )
    assert ingest.status_code == 201

    resp = client.get(
        "/logs",
        headers=admin_token,
        params={"rule_id": 942100, "action": "deny"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["producer_event_id"] == "coraza-event-3"

