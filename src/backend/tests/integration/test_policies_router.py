"""Testy integracyjne routera policies (CRUD + autoryzacja)."""

from typing import Any

from fastapi.testclient import TestClient

from app.models.user import User


def _create_policy(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Default Policy",
    description: str = "Domyslna polityka",
    paranoia_level: int = 2,
    inbound_anomaly_threshold: int = 5,
    outbound_anomaly_threshold: int = 5,
    enforcement_mode: str = "block",
) -> dict[str, Any]:
    """Pomocniczo tworzy politykę i zwraca body JSON."""
    resp = client.post(
        "/policies",
        headers=headers,
        json={
            "name": name,
            "description": description,
            "paranoia_level": paranoia_level,
            "inbound_anomaly_threshold": inbound_anomaly_threshold,
            "outbound_anomaly_threshold": outbound_anomaly_threshold,
            "enforcement_mode": enforcement_mode,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# POST /policies
# ---------------------------------------------------------------------------


def test_create_policy_admin_returns_201(
    client: TestClient, admin_token: dict[str, str], admin_user: User
) -> None:
    """Admin może utworzyć politykę."""
    resp = client.post(
        "/policies",
        headers=admin_token,
        json={
            "name": "Strict",
            "description": "Wysoka ochrona",
            "paranoia_level": 4,
            "inbound_anomaly_threshold": 7,
            "outbound_anomaly_threshold": 8,
            "enforcement_mode": "detect_only",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 0
    assert body["name"] == "Strict"
    assert body["description"] == "Wysoka ochrona"
    assert body["paranoia_level"] == 4
    assert body["inbound_anomaly_threshold"] == 7
    assert body["outbound_anomaly_threshold"] == 8
    assert body["enforcement_mode"] == "detect_only"
    assert body["is_active"] is True
    assert body["created_by"] == admin_user.id


def test_create_policy_viewer_forbidden(
    client: TestClient, viewer_token: dict[str, str]
) -> None:
    """Viewer nie może tworzyć polityki."""
    resp = client.post(
        "/policies",
        headers=viewer_token,
        json={
            "name": "Viewer policy",
            "paranoia_level": 1,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_create_policy_duplicate_name_returns_409(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Druga polityka o tej samej nazwie -> 409."""
    _create_policy(client, admin_token, name="Duplicate")

    resp = client.post(
        "/policies",
        headers=admin_token,
        json={
            "name": "Duplicate",
            "paranoia_level": 2,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
        },
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Policy name already exists"


def test_create_policy_invalid_paranoia_level_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Out-of-range paranoia_level should be rejected at router validation."""
    resp = client.post(
        "/policies",
        headers=admin_token,
        json={
            "name": "Invalid paranoia",
            "paranoia_level": 5,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
        },
    )
    assert resp.status_code == 422


def test_create_policy_default_ddos_settings(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """A policy created without DDoS fields gets safe, protection-off defaults."""
    body = _create_policy(client, admin_token, name="No DDoS overrides")

    assert body["ddos_protection_enabled"] is False
    assert body["rate_limit_requests"] == 100
    assert body["rate_limit_window_seconds"] == 10
    assert body["max_connections_per_ip"] == 20


def test_create_policy_with_ddos_settings_returns_201(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """DDoS fields round-trip through creation."""
    resp = client.post(
        "/policies",
        headers=admin_token,
        json={
            "name": "DDoS Hardened",
            "paranoia_level": 2,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
            "ddos_protection_enabled": True,
            "rate_limit_requests": 50,
            "rate_limit_window_seconds": 5,
            "max_connections_per_ip": 10,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["ddos_protection_enabled"] is True
    assert body["rate_limit_requests"] == 50
    assert body["rate_limit_window_seconds"] == 5
    assert body["max_connections_per_ip"] == 10


def test_create_policy_invalid_rate_limit_requests_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Out-of-range rate_limit_requests should be rejected at router validation."""
    resp = client.post(
        "/policies",
        headers=admin_token,
        json={
            "name": "Invalid rate limit",
            "paranoia_level": 2,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
            "rate_limit_requests": 0,
        },
    )
    assert resp.status_code == 422


def test_create_policy_invalid_rate_limit_window_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Out-of-range rate_limit_window_seconds is rejected at router validation."""
    resp = client.post(
        "/policies",
        headers=admin_token,
        json={
            "name": "Invalid window",
            "paranoia_level": 2,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
            "rate_limit_window_seconds": 3601,
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /policies
# ---------------------------------------------------------------------------


def test_list_policies_admin_returns_200(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Admin can list policies with pagination metadata."""
    _create_policy(client, admin_token, name="P1")
    _create_policy(client, admin_token, name="P2")

    resp = client.get("/policies", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["per_page"] == 50
    assert [item["name"] for item in body["items"]] == ["P1", "P2"]


def test_list_policies_viewer_returns_200(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """Viewer ma dostęp tylko do odczytu listy."""
    _create_policy(client, admin_token, name="Readable")

    resp = client.get("/policies", headers=viewer_token)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


def test_list_policies_requires_auth(client: TestClient) -> None:
    """Brak tokena -> 401."""
    resp = client.get("/policies")
    assert resp.status_code == 401


def test_list_policies_paginates_with_page_and_per_page(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """page/per_page parameters return a slice of results."""
    for index in range(3):
        _create_policy(client, admin_token, name=f"Policy {index}")

    resp = client.get("/policies?page=2&per_page=2", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 2
    assert body["per_page"] == 2
    assert [item["name"] for item in body["items"]] == ["Policy 2"]


def test_list_policies_filters_by_q(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """q filters policies by a name substring."""
    _create_policy(client, admin_token, name="Strict Web App")
    _create_policy(client, admin_token, name="Relaxed API")

    resp = client.get("/policies?q=web", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 1
    assert [item["name"] for item in body["items"]] == ["Strict Web App"]


# ---------------------------------------------------------------------------
# GET /policies/{policy_id}
# ---------------------------------------------------------------------------


def test_get_policy_returns_detail_with_rule_overrides(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Szczegóły policy zawierają pole rule_overrides."""
    created = _create_policy(client, admin_token, name="Detail")

    resp = client.get(f"/policies/{created['id']}", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Detail"
    assert "rule_overrides" in body
    assert body["rule_overrides"] == []


def test_get_policy_not_found_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Brak policy o danym ID -> 404."""
    resp = client.get("/policies/99999", headers=admin_token)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


# ---------------------------------------------------------------------------
# PATCH /policies/{policy_id}
# ---------------------------------------------------------------------------


def test_patch_policy_admin_partial_update(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH aktualizuje tylko podane pola."""
    created = _create_policy(
        client,
        admin_token,
        name="Patch me",
        description="Opis",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
    )

    resp = client.patch(
        f"/policies/{created['id']}",
        headers=admin_token,
        json={"paranoia_level": 3, "is_active": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Patch me"
    assert body["description"] == "Opis"
    assert body["paranoia_level"] == 3
    assert body["inbound_anomaly_threshold"] == 5
    assert body["outbound_anomaly_threshold"] == 5
    assert body["is_active"] is False


def test_patch_policy_updates_ddos_settings(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH updates DDoS protection fields."""
    created = _create_policy(client, admin_token, name="Patch DDoS")

    resp = client.patch(
        f"/policies/{created['id']}",
        headers=admin_token,
        json={
            "ddos_protection_enabled": True,
            "rate_limit_requests": 200,
            "rate_limit_window_seconds": 30,
            "max_connections_per_ip": 40,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ddos_protection_enabled"] is True
    assert body["rate_limit_requests"] == 200
    assert body["rate_limit_window_seconds"] == 30
    assert body["max_connections_per_ip"] == 40


def test_patch_policy_viewer_forbidden(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Viewer nie może modyfikować policy."""
    created = _create_policy(client, admin_token, name="No patch")

    resp = client.patch(
        f"/policies/{created['id']}",
        headers=viewer_token,
        json={"name": "Blocked"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_patch_policy_duplicate_name_returns_409(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Zmiana nazwy na istniejącą -> 409."""
    _create_policy(client, admin_token, name="Alpha")
    p2 = _create_policy(client, admin_token, name="Beta")

    resp = client.patch(
        f"/policies/{p2['id']}",
        headers=admin_token,
        json={"name": "Alpha"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Policy name already exists"


def test_patch_policy_not_found_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH nieistniejącej policy -> 404."""
    resp = client.patch(
        "/policies/99999",
        headers=admin_token,
        json={"name": "Nope"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_patch_policy_name_null_returns_422(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH z name=null powinien być odrzucony jako 422."""
    created = _create_policy(client, admin_token, name="Null Name")

    resp = client.patch(
        f"/policies/{created['id']}",
        headers=admin_token,
        json={"name": None},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Field 'name' cannot be null"


def test_patch_policy_paranoia_level_null_returns_422(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH z paranoia_level=null powinien być odrzucony jako 422."""
    created = _create_policy(client, admin_token, name="Null Paranoia")

    resp = client.patch(
        f"/policies/{created['id']}",
        headers=admin_token,
        json={"paranoia_level": None},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Field 'paranoia_level' cannot be null"


def test_patch_policy_invalid_paranoia_level_returns_422(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Out-of-range paranoia_level should be rejected before service update."""
    created = _create_policy(client, admin_token, name="Invalid Patch Paranoia")

    resp = client.patch(
        f"/policies/{created['id']}",
        headers=admin_token,
        json={"paranoia_level": 0},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /policies/{policy_id}
# ---------------------------------------------------------------------------


def test_delete_policy_admin_returns_204(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Admin może usunąć policy."""
    created = _create_policy(client, admin_token, name="Delete me")

    resp = client.delete(f"/policies/{created['id']}", headers=admin_token)
    assert resp.status_code == 204
    assert resp.text == ""

    get_resp = client.get(f"/policies/{created['id']}", headers=admin_token)
    assert get_resp.status_code == 404


def test_delete_policy_assigned_to_vhost_returns_409(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Assigned policies cannot be deleted."""
    created = _create_policy(client, admin_token, name="Assigned policy")
    vhost_resp = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "assigned.example.com",
            "backend_url": "http://localhost:8080",
            "policy_id": created["id"],
        },
    )
    assert vhost_resp.status_code == 201

    resp = client.delete(f"/policies/{created['id']}", headers=admin_token)

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Policy is assigned to a virtual host"


def test_delete_policy_viewer_forbidden(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Viewer nie może usuwać policy."""
    created = _create_policy(client, admin_token, name="No delete")

    resp = client.delete(f"/policies/{created['id']}", headers=viewer_token)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_delete_policy_not_found_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """DELETE nieistniejącej policy -> 404."""
    resp = client.delete("/policies/99999", headers=admin_token)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"
