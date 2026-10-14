from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.runtime_operation import (
    RuntimeOperation,
    RuntimeOperationStatus,
    RuntimeOperationType,
)
from app.models.vhost import VHost


def test_runtime_status_requires_auth(client: TestClient) -> None:
    response = client.get("/runtime/status")

    assert response.status_code == 401


def test_runtime_status_allows_viewer(
    client: TestClient,
    viewer_token: dict[str, str],
) -> None:
    response = client.get("/runtime/status", headers=viewer_token)

    assert response.status_code == 200


def test_runtime_status_returns_never_deployed_for_empty_state(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    response = client.get("/runtime/status", headers=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["frontend_contract_version"] == "1"
    assert body["deployment_state"] == "never_deployed"
    assert body["generated_config"]["can_generate"] is True
    assert len(body["generated_config"]["checksum"]) == 64
    assert body["latest_validation"] is None
    assert body["latest_reload"] is None


def test_runtime_status_returns_latest_validation_and_reload(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
) -> None:
    db.add(
        RuntimeOperation(
            operation_type=RuntimeOperationType.validation,
            status=RuntimeOperationStatus.success,
            config_checksum="1" * 64,
            message="Config validated successfully",
        )
    )
    db.add(
        RuntimeOperation(
            operation_type=RuntimeOperationType.reload,
            status=RuntimeOperationStatus.success,
            config_checksum="2" * 64,
            message="HAProxy reloaded",
        )
    )
    db.commit()

    response = client.get("/runtime/status", headers=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["deployment_state"] == "deployed"
    assert body["latest_validation"]["status"] == "success"
    assert body["latest_validation"]["message"] == "Config validated successfully"
    assert body["latest_reload"]["status"] == "success"
    assert body["latest_reload"]["message"] == "HAProxy reloaded"


def test_runtime_status_reports_generation_error_for_invalid_vhost_data(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
) -> None:
    # This simulates invalid persisted data bypassing API validation.
    db.add(
        VHost(
            domain="broken.example.com",
            backend_url="http://",
            is_active=True,
            ssl_enabled=False,
            policy_id=None,
        )
    )
    db.commit()

    response = client.get("/runtime/status", headers=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["generated_config"]["can_generate"] is False
    assert "missing host" in body["generated_config"]["error"]


def test_runtime_status_generates_config_for_multiple_active_vhosts(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
) -> None:
    db.add_all(
        [
            VHost(
                domain="app.example.com",
                backend_url="http://app-backend:8000",
                is_active=True,
                ssl_enabled=False,
                policy_id=None,
            ),
            VHost(
                domain="api.example.com",
                backend_url="http://api-backend:8000",
                is_active=True,
                ssl_enabled=False,
                policy_id=None,
            ),
        ]
    )
    db.commit()

    response = client.get("/runtime/status", headers=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["generated_config"]["can_generate"] is True
    assert len(body["generated_config"]["checksum"]) == 64
    assert body["generated_config"]["generated_at"] is not None
    assert body["generated_config"]["error"] is None


# ---------------------------------------------------------------------------
# active_config — what HAProxy and Coraza are actually running from (#315)
# ---------------------------------------------------------------------------


def _point_runtime_root_at(monkeypatch, runtime_root: Path) -> Path:
    runtime_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        settings, "runtime_generated_config_root", str(runtime_root)
    )
    return runtime_root / "current"


def test_active_config_reports_missing_release_as_degraded(
    client: TestClient,
    admin_token: dict[str, str],
    tmp_path: Path,
    monkeypatch,
) -> None:
    _point_runtime_root_at(monkeypatch, tmp_path / "generated")

    body = client.get("/runtime/status", headers=admin_token).json()

    assert body["active_config"]["haproxy_source"] == "missing"
    assert body["active_config"]["coraza_source"] == "fallback"
    assert body["active_config"]["degraded"] is True
    assert "no release is deployed" in body["active_config"]["warning"].lower()


def test_active_config_reports_a_generated_release_as_healthy(
    client: TestClient,
    admin_token: dict[str, str],
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    release = runtime_root / "releases" / "abc"
    release.mkdir(parents=True)
    (release / "haproxy.cfg").write_text("global\n", encoding="utf-8")
    (release / "coraza-spoa.yaml").write_text(
        "applications: []\n", encoding="utf-8"
    )
    current = _point_runtime_root_at(monkeypatch, runtime_root)
    current.symlink_to("releases/abc")

    body = client.get("/runtime/status", headers=admin_token).json()

    assert body["active_config"] == {
        "haproxy_source": "generated",
        "coraza_source": "generated",
        "degraded": False,
        "warning": None,
    }


def test_active_config_reports_the_demo_seed_release_as_degraded(
    client: TestClient,
    admin_token: dict[str, str],
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    seed = runtime_root / "releases" / "seed"
    seed.mkdir(parents=True)
    (seed / "haproxy.cfg").write_text("global\n", encoding="utf-8")
    current = _point_runtime_root_at(monkeypatch, runtime_root)
    current.symlink_to("releases/seed")

    body = client.get("/runtime/status", headers=admin_token).json()

    assert body["active_config"]["haproxy_source"] == "seed"
    assert body["active_config"]["degraded"] is True
    assert "demo seed configuration" in body["active_config"]["warning"]


def test_active_config_reports_coraza_fallback_warning(
    client: TestClient,
    admin_token: dict[str, str],
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    release = runtime_root / "releases" / "old"
    release.mkdir(parents=True)
    (release / "haproxy.cfg").write_text("global\n", encoding="utf-8")
    current = _point_runtime_root_at(monkeypatch, runtime_root)
    current.symlink_to("releases/old")

    body = client.get("/runtime/status", headers=admin_token).json()

    assert body["active_config"]["haproxy_source"] == "generated"
    assert body["active_config"]["coraza_source"] == "fallback"
    assert body["active_config"]["degraded"] is True
    assert "detect-only" in body["active_config"]["warning"]
