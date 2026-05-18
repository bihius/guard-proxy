"""Integration tests for POST /config/apply."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings


def _mock_validate_ok(_: Path) -> SimpleNamespace:
    return SimpleNamespace(ok=True, output="Configuration file is valid")


def _mock_reload_ok() -> SimpleNamespace:
    return SimpleNamespace(ok=True, output="Reload succeeded")


def _mock_validate_fail(_: Path) -> SimpleNamespace:
    return SimpleNamespace(ok=False, output="line 42 parse error")


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_apply_admin_success(
    client: TestClient,
    admin_token: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "runtime_generated_config_root",
        str(tmp_path / "generated"),
    )
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        _mock_validate_ok,
    )
    monkeypatch.setattr("app.services.config_apply._reload_haproxy", _mock_reload_ok)

    resp = client.post("/config/apply", headers=admin_token)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert len(body["correlation_id"]) == 32
    assert "checksum" in body
    assert "message" in body
    gc = body["generated_config"]
    assert "haproxy_cfg" in gc
    assert "crs_setup_conf" in gc
    assert "rule_overrides_conf" in gc


# ---------------------------------------------------------------------------
# Auth / role checks
# ---------------------------------------------------------------------------


def test_apply_viewer_returns_403(
    client: TestClient,
    viewer_token: dict[str, str],
) -> None:
    resp = client.post("/config/apply", headers=viewer_token)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_apply_unauthenticated_returns_401(client: TestClient) -> None:
    resp = client.post("/config/apply")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation failure path
# ---------------------------------------------------------------------------


def test_apply_validation_failure(
    client: TestClient,
    admin_token: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "runtime_generated_config_root",
        str(tmp_path / "generated"),
    )
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        _mock_validate_fail,
    )
    monkeypatch.setattr("app.services.config_apply._reload_haproxy", _mock_reload_ok)

    resp = client.post("/config/apply", headers=admin_token)

    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == "validation_failed"
    assert "parse error" in body["validation_output"]
