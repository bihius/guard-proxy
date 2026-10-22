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
    assert data["checks"]["database"]["detail"] == "database unavailable"


# ---------------------------------------------------------------------------
# /ready — readiness probe (config dir failure)
# ---------------------------------------------------------------------------


def test_ready_returns_503_when_config_dir_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Missing config dir → 503 with a generic detail; the path stays in logs."""
    config_root = "/nonexistent/guard-proxy-test-path"
    monkeypatch.setattr(
        main_module.settings,
        "runtime_generated_config_root",
        config_root,
    )

    with caplog.at_level("ERROR"):
        response = client.get("/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not ready"
    assert data["checks"]["runtime_config"]["status"] == "error"
    assert data["checks"]["runtime_config"]["detail"] == (
        "runtime config directory is not writable"
    )
    assert config_root not in response.text
    assert config_root in caplog.text
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


# ---------------------------------------------------------------------------
# Seed config version stamp (issue #312)
# ---------------------------------------------------------------------------


def test_health_reports_degraded_for_a_stale_seed_config(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale = tmp_path / "coraza.cfg"
    stale.write_text("[coraza]\nspoe-message coraza-req\n    args app=str(default)\n")
    monkeypatch.setattr(main_module.settings, "seed_coraza_config_path", str(stale))

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert str(stale) in data["detail"]


def test_health_is_healthy_for_the_current_seed_config(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_config = (
        Path(main_module.__file__).resolve().parents[3] / "configs/haproxy/coraza.cfg"
    )
    monkeypatch.setattr(
        main_module.settings, "seed_coraza_config_path", str(repo_config)
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ready_returns_503_for_a_stale_seed_config(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The release kit healthcheck calls /ready, so a tag-only upgrade fails it.

    The body stays generic like the other readiness checks; the stale path is
    logged server-side and stays available to admins through `/health`,
    `/runtime/status` and the `POST /config/apply` error.
    """
    stale = tmp_path / "coraza.cfg"
    stale.write_text("[coraza]\n")
    monkeypatch.setattr(
        main_module.settings, "runtime_generated_config_root", str(tmp_path)
    )
    monkeypatch.setattr(main_module.settings, "seed_coraza_config_path", str(stale))

    with caplog.at_level("ERROR", logger="app.main"):
        response = client.get("/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["checks"]["seed_config"]["status"] == "error"
    assert data["checks"]["seed_config"]["detail"] == (
        "seed config version does not match this image"
    )
    assert str(stale) not in response.text
    assert data["checks"]["database"]["status"] == "ok"
    assert str(stale) in caplog.text
