"""Integration tests for the /health liveness and /ready readiness probes."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import app.main as main_module
from app.database import get_db
from app.main import app


# ---------------------------------------------------------------------------
# /health — liveness probe
# ---------------------------------------------------------------------------


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_health_does_not_require_auth(client: TestClient) -> None:
    """Liveness probe must be accessible without authentication."""
    response = client.get("/health")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /ready — readiness probe (happy path)
# ---------------------------------------------------------------------------


def test_ready_returns_200_when_all_checks_pass(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both DB and config-dir checks pass → 200 with all checks ok."""
    monkeypatch.setattr(
        main_module.settings, "runtime_generated_config_root", str(tmp_path)
    )

    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"]["status"] == "ok"
    assert data["checks"]["runtime_config"]["status"] == "ok"


def test_ready_does_not_require_auth(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness probe must be accessible without authentication."""
    monkeypatch.setattr(
        main_module.settings, "runtime_generated_config_root", str(tmp_path)
    )
    response = client.get("/ready")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /ready — readiness probe (DB failure)
# ---------------------------------------------------------------------------


def test_ready_returns_503_when_db_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DB connectivity failure → 503 with database check reporting error."""
    monkeypatch.setattr(
        main_module.settings, "runtime_generated_config_root", str(tmp_path)
    )

    mock_session = MagicMock(spec=Session)
    mock_session.execute.side_effect = SQLAlchemyError("connection refused")

    def broken_db() -> Iterator[Session]:
        yield mock_session

    app.dependency_overrides[get_db] = broken_db
    try:
        with TestClient(app) as c:
            response = c.get("/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not ready"
    assert data["checks"]["database"]["status"] == "error"
    assert "detail" in data["checks"]["database"]


# ---------------------------------------------------------------------------
# /ready — readiness probe (config dir failure)
# ---------------------------------------------------------------------------


def test_ready_returns_503_when_config_dir_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing config dir → 503 with runtime_config check reporting error."""
    monkeypatch.setattr(
        main_module.settings,
        "runtime_generated_config_root",
        "/nonexistent/guard-proxy-test-path",
    )

    response = client.get("/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not ready"
    assert data["checks"]["runtime_config"]["status"] == "error"
    assert "detail" in data["checks"]["runtime_config"]
    # DB check should still have passed
    assert data["checks"]["database"]["status"] == "ok"


def test_ready_body_includes_both_checks_on_full_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both checks fail the body contains entries for both."""
    monkeypatch.setattr(
        main_module.settings,
        "runtime_generated_config_root",
        "/nonexistent/guard-proxy-test-path",
    )

    mock_session = MagicMock(spec=Session)
    mock_session.execute.side_effect = SQLAlchemyError("unreachable")

    def broken_db() -> Iterator[Session]:
        yield mock_session

    app.dependency_overrides[get_db] = broken_db
    try:
        with TestClient(app) as c:
            response = c.get("/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    data = response.json()
    assert data["checks"]["database"]["status"] == "error"
    assert data["checks"]["runtime_config"]["status"] == "error"
