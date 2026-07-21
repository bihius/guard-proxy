"""Integration tests for the /security ban-list endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.models.vhost import VHost
from app.services import ban_list_service


def _create_banned_vhost(db: Session) -> VHost:
    policy = Policy(
        name="Auto-ban policy",
        ddos_protection_enabled=True,
        rate_limit_requests=100,
        rate_limit_window_seconds=10,
        max_connections_per_ip=20,
        auto_ban_enabled=True,
        ban_threshold=10,
        ban_duration_seconds=600,
    )
    vhost = VHost(
        domain="app.example.com",
        backend_url="http://backend:8000",
        is_active=True,
        ssl_enabled=False,
        policy=policy,
    )
    db.add_all([policy, vhost])
    db.commit()
    return vhost


def test_list_banned_ips_requires_auth(client: TestClient) -> None:
    response = client.get("/security/banned-ips")

    assert response.status_code == 401


def test_list_banned_ips_forbidden_for_viewer(
    client: TestClient, viewer_token: dict[str, str]
) -> None:
    response = client.get("/security/banned-ips", headers=viewer_token)

    assert response.status_code == 403


def test_list_banned_ips_returns_entries_for_admin(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vhost = _create_banned_vhost(db)

    monkeypatch.setattr(
        ban_list_service,
        "_send_runtime_command",
        lambda _cmd: "0x1: key=203.0.113.5 use=0 exp=60000 gpc0=99\n",
    )

    response = client.get("/security/banned-ips", headers=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"] == [
        {
            "ip": "203.0.113.5",
            "vhost_id": vhost.id,
            "domain": "app.example.com",
            "gpc0": 99,
            "ban_threshold": 10,
            "banned": True,
            "expires_in_seconds": 60,
        }
    ]


def test_list_banned_ips_returns_empty_when_nothing_tracked(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    response = client.get("/security/banned-ips", headers=admin_token)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_list_banned_ips_returns_502_when_runtime_api_unreachable(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_banned_vhost(db)

    def fake_send(_command: str) -> str:
        raise ban_list_service.RuntimeApiError("connection refused")

    monkeypatch.setattr(ban_list_service, "_send_runtime_command", fake_send)

    response = client.get("/security/banned-ips", headers=admin_token)

    assert response.status_code == 502


def test_unban_requires_auth(client: TestClient) -> None:
    response = client.delete("/security/banned-ips/203.0.113.5")

    assert response.status_code == 401


def test_unban_forbidden_for_viewer(
    client: TestClient, viewer_token: dict[str, str]
) -> None:
    response = client.delete(
        "/security/banned-ips/203.0.113.5", headers=viewer_token
    )

    assert response.status_code == 403


def test_unban_clears_entry_for_admin(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_banned_vhost(db)
    monkeypatch.setattr(ban_list_service, "_send_runtime_command", lambda _cmd: "")

    response = client.delete("/security/banned-ips/203.0.113.5", headers=admin_token)

    assert response.status_code == 200
    assert response.json() == {"ip": "203.0.113.5", "cleared": 1}


def test_unban_returns_422_for_invalid_ip(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    response = client.delete("/security/banned-ips/not-an-ip", headers=admin_token)

    assert response.status_code == 422


def test_unban_returns_502_when_runtime_api_unreachable(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_banned_vhost(db)

    def fake_send(_command: str) -> str:
        raise ban_list_service.RuntimeApiError("connection refused")

    monkeypatch.setattr(ban_list_service, "_send_runtime_command", fake_send)

    response = client.delete("/security/banned-ips/203.0.113.5", headers=admin_token)

    assert response.status_code == 502
