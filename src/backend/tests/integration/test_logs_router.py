"""Testy integracyjne routera logs (filtrowanie + paginacja)."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.log import Log, LogSeverity


def _create_log(
    db: Session,
    *,
    logged_at: datetime,
    vhost: str,
    severity: LogSeverity,
    message: str,
) -> Log:
    """Pomocniczo zapisuje log w bazie testowej."""
    log = Log(
        logged_at=logged_at,
        vhost=vhost,
        severity=severity,
        message=message,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def test_list_logs_returns_paginated_results_for_admin(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """Admin może pobrać logi, a odpowiedź ma metadane paginacji."""
    older = _create_log(
        db,
        logged_at=datetime(2026, 3, 20, 10, 0, 0),
        vhost="app.example.com",
        severity=LogSeverity.warning,
        message="Older event",
    )
    newer = _create_log(
        db,
        logged_at=datetime(2026, 3, 21, 10, 0, 0),
        vhost="app.example.com",
        severity=LogSeverity.error,
        message="Newer event",
    )

    resp = client.get("/logs", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert [item["id"] for item in body["items"]] == [newer.id, older.id]


def test_list_logs_viewer_has_read_access(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Viewer ma dostęp read-only do logów."""
    _create_log(
        db,
        logged_at=datetime(2026, 3, 21, 10, 0, 0),
        vhost="frontend.example.com",
        severity=LogSeverity.info,
        message="Rendered dashboard",
    )

    resp = client.get("/logs", headers=viewer_token)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_logs_requires_auth(client: TestClient) -> None:
    """Brak tokena -> 401."""
    resp = client.get("/logs")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_list_logs_filters_by_vhost_and_severity(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """API zwraca tylko rekordy pasujące do obu filtrów naraz."""
    _create_log(
        db,
        logged_at=datetime(2026, 3, 21, 8, 0, 0),
        vhost="api.example.com",
        severity=LogSeverity.error,
        message="Matched",
    )
    _create_log(
        db,
        logged_at=datetime(2026, 3, 21, 9, 0, 0),
        vhost="api.example.com",
        severity=LogSeverity.info,
        message="Wrong severity",
    )
    _create_log(
        db,
        logged_at=datetime(2026, 3, 21, 10, 0, 0),
        vhost="www.example.com",
        severity=LogSeverity.error,
        message="Wrong vhost",
    )

    resp = client.get(
        "/logs",
        headers=admin_token,
        params={"vhost": "api.example.com", "severity": "error"},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["message"] == "Matched"


def test_list_logs_filters_by_date_range(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """Zakres dat ogranicza wyniki do wpisów z wybranego przedziału."""
    _create_log(
        db,
        logged_at=datetime(2026, 3, 19, 23, 59, 59),
        vhost="api.example.com",
        severity=LogSeverity.warning,
        message="Too early",
    )
    _create_log(
        db,
        logged_at=datetime(2026, 3, 20, 12, 0, 0),
        vhost="api.example.com",
        severity=LogSeverity.warning,
        message="In range",
    )
    _create_log(
        db,
        logged_at=datetime(2026, 3, 22, 0, 0, 1),
        vhost="api.example.com",
        severity=LogSeverity.warning,
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


def test_list_logs_paginates_results(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
) -> None:
    """page i page_size wybierają właściwy wycinek wyniku."""
    first = _create_log(
        db,
        logged_at=datetime(2026, 3, 21, 8, 0, 0),
        vhost="api.example.com",
        severity=LogSeverity.info,
        message="First",
    )
    second = _create_log(
        db,
        logged_at=datetime(2026, 3, 21, 9, 0, 0),
        vhost="api.example.com",
        severity=LogSeverity.warning,
        message="Second",
    )
    third = _create_log(
        db,
        logged_at=datetime(2026, 3, 21, 10, 0, 0),
        vhost="api.example.com",
        severity=LogSeverity.error,
        message="Third",
    )

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
    assert body["items"][0]["id"] != third.id
    assert body["items"][0]["id"] != first.id


def test_list_logs_rejects_invalid_date_range(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """date_from późniejsze niż date_to -> 422."""
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
