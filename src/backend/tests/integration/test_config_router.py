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
    assert "applications:" in gc["coraza_spoa_yaml"]
    assert [app["name"] for app in gc["coraza_apps"]] == ["default"]


def test_apply_writes_a_coraza_app_per_vhost_policy(
    client: TestClient,
    admin_token: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each vhost's policy reaches Coraza as its own application."""
    runtime_root = tmp_path / "generated"
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        _mock_validate_ok,
    )
    monkeypatch.setattr("app.services.config_apply._reload_haproxy", _mock_reload_ok)
    policy_ids: dict[str, int] = {}
    for domain, paranoia_level, mode in (
        ("shop.example.com", 3, "block"),
        ("blog.example.com", 1, "detect_only"),
    ):
        policy = client.post(
            "/policies",
            headers=admin_token,
            json={
                "name": f"{domain} policy",
                "paranoia_level": paranoia_level,
                "inbound_anomaly_threshold": 5,
                "outbound_anomaly_threshold": 4,
                "enforcement_mode": mode,
            },
        ).json()
        policy_ids[domain] = policy["id"]
        created = client.post(
            "/vhosts",
            headers=admin_token,
            json={
                "domain": domain,
                "backend_url": "http://app:8080",
                "policy_id": policy["id"],
            },
        )
        assert created.status_code == 201
    disabled = client.post(
        f"/policies/{policy_ids['shop.example.com']}/rules",
        headers=admin_token,
        json={"rule_id": 942100, "action": "disable"},
    )
    assert disabled.status_code == 201

    resp = client.post("/config/apply", headers=admin_token)

    assert resp.status_code == 200
    apps_dir = runtime_root / "current" / "coraza"
    shop_dir = apps_dir / f"policy_{policy_ids['shop.example.com']}"
    blog_dir = apps_dir / f"policy_{policy_ids['blog.example.com']}"
    shop_setup = (shop_dir / "crs-setup.conf").read_text(encoding="utf-8")
    blog_setup = (blog_dir / "crs-setup.conf").read_text(encoding="utf-8")
    assert "SecRuleEngine On" in shop_setup
    assert "tx.blocking_paranoia_level=3" in shop_setup
    assert "SecRuleEngine DetectionOnly" in blog_setup
    assert "tx.blocking_paranoia_level=1" in blog_setup
    assert "SecRuleRemoveById 942100" in (shop_dir / "rule-overrides.conf").read_text(
        encoding="utf-8"
    )
    assert "942100" not in (blog_dir / "rule-overrides.conf").read_text(
        encoding="utf-8"
    )


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


def test_apply_with_an_inactive_assigned_policy_explains_instead_of_500(
    client: TestClient,
    admin_token: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuration the generator cannot render is a 422 with the reason."""
    monkeypatch.setattr(
        settings,
        "runtime_generated_config_root",
        str(tmp_path / "generated"),
    )
    reloads: list[None] = []
    monkeypatch.setattr(
        "app.services.config_apply._reload_haproxy",
        lambda: reloads.append(None) or _mock_reload_ok(),
    )
    policy = client.post(
        "/policies",
        headers=admin_token,
        json={
            "name": "Draft policy",
            "paranoia_level": 1,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 4,
        },
    ).json()
    created = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "a.example.com",
            "backend_url": "http://app:8080",
            "policy_id": policy["id"],
        },
    )
    assert created.status_code == 201
    deactivated = client.patch(
        f"/policies/{policy['id']}",
        headers=admin_token,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200

    resp = client.post("/config/apply", headers=admin_token)

    assert resp.status_code == 422
    assert "inactive policy" in resp.json()["detail"]
    assert reloads == []


# ---------------------------------------------------------------------------
# Runtime operation recording (deployment status)
# ---------------------------------------------------------------------------


def test_apply_success_marks_runtime_status_deployed(
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

    apply_resp = client.post("/config/apply", headers=admin_token)
    assert apply_resp.status_code == 200

    status_resp = client.get("/runtime/status", headers=admin_token)
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["deployment_state"] == "deployed"
    assert body["latest_validation"]["status"] == "success"
    assert body["latest_reload"]["status"] == "success"
    assert body["latest_reload"]["config_checksum"] == apply_resp.json()["checksum"]


def test_apply_validation_failure_records_failed_validation_only(
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

    apply_resp = client.post("/config/apply", headers=admin_token)
    assert apply_resp.status_code == 422

    status_resp = client.get("/runtime/status", headers=admin_token)
    assert status_resp.status_code == 200
    body = status_resp.json()
    # No reload was attempted, so the deployment state is unchanged.
    assert body["deployment_state"] == "never_deployed"
    assert body["latest_validation"]["status"] == "failed"
    assert body["latest_reload"] is None
