"""Integration tests for POST /geoip/refresh (issue #175)."""

from __future__ import annotations

import threading

from fastapi.testclient import TestClient


def _fake_result(**overrides: object):
    from app.services.geoip_service import GeoipRefreshResult

    defaults: dict[str, object] = {
        "downloaded": True,
        "entries": 42,
        "changed": True,
        "reloaded": True,
        "message": "GeoIP database refreshed: 42 entries written.",
    }
    defaults.update(overrides)
    return GeoipRefreshResult(**defaults)  # type: ignore[arg-type]


def test_refresh_admin_returns_serialized_result(
    client: TestClient,
    admin_token: dict[str, str],
    monkeypatch,
) -> None:
    # Patch below the lock so try_refresh()'s real locking still runs.
    monkeypatch.setattr(
        "app.services.geoip_service._refresh_locked",
        lambda force_reload: _fake_result(),
    )

    resp = client.post("/geoip/refresh", headers=admin_token)

    assert resp.status_code == 200
    body = resp.json()
    assert body["downloaded"] is True
    assert body["entries"] == 42
    assert body["changed"] is True
    assert body["reloaded"] is True
    assert body["message"] == "GeoIP database refreshed: 42 entries written."


def test_refresh_unauthenticated_returns_401(client: TestClient) -> None:
    resp = client.post("/geoip/refresh")
    assert resp.status_code == 401


def test_refresh_viewer_returns_403(
    client: TestClient, viewer_token: dict[str, str]
) -> None:
    resp = client.post("/geoip/refresh", headers=viewer_token)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_refresh_concurrent_call_returns_409(
    client: TestClient,
    admin_token: dict[str, str],
    monkeypatch,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def _slow_refresh(force_reload):
        started.set()
        release.wait(timeout=5)
        return _fake_result()

    # Patched below the lock, so this exercises the real service-level lock —
    # the same one the scheduled job contends for.
    monkeypatch.setattr("app.services.geoip_service._refresh_locked", _slow_refresh)

    first_call_result: dict[str, int] = {}

    def _run_first_call() -> None:
        resp = client.post("/geoip/refresh", headers=admin_token)
        first_call_result["status_code"] = resp.status_code

    thread = threading.Thread(target=_run_first_call)
    thread.start()
    started.wait(timeout=5)

    try:
        second_resp = client.post("/geoip/refresh", headers=admin_token)
        assert second_resp.status_code == 409
    finally:
        release.set()
        thread.join(timeout=5)

    assert first_call_result.get("status_code") == 200
