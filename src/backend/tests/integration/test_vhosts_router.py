"""Testy integracyjne routera vhosts (CRUD + autoryzacja)."""

from typing import Any

from fastapi.testclient import TestClient

from app.models.user import User


def _create_policy(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Default Policy",
) -> dict[str, Any]:
    """Pomocniczo tworzy politykę do przypisania vhostowi."""
    resp = client.post(
        "/policies",
        headers=headers,
        json={
            "name": name,
            "description": "Policy for vhosts",
            "paranoia_level": 2,
            "anomaly_threshold": 5,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_vhost(
    client: TestClient,
    headers: dict[str, str],
    *,
    domain: str = "example.com",
    backend_url: str = "http://localhost:8080",
    description: str | None = "Primary site",
    ssl_enabled: bool = False,
    is_active: bool = True,
    policy_id: int | None = None,
) -> dict[str, Any]:
    """Pomocniczo tworzy vhost i zwraca body JSON."""
    resp = client.post(
        "/vhosts",
        headers=headers,
        json={
            "domain": domain,
            "backend_url": backend_url,
            "description": description,
            "ssl_enabled": ssl_enabled,
            "is_active": is_active,
            "policy_id": policy_id,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# POST /vhosts
# ---------------------------------------------------------------------------


def test_create_vhost_admin_returns_201(
    client: TestClient,
    admin_token: dict[str, str],
    admin_user: User,
) -> None:
    """Admin może utworzyć vhost."""
    policy = _create_policy(client, admin_token, name="Assigned")

    resp = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "App.Example.com",
            "backend_url": "http://localhost:3000",
            "description": "Main app",
            "ssl_enabled": True,
            "is_active": True,
            "policy_id": policy["id"],
        },
    )
    assert resp.status_code == 201

    body = resp.json()
    assert body["id"] > 0
    assert body["domain"] == "app.example.com"
    assert body["backend_url"] == "http://localhost:3000"
    assert body["description"] == "Main app"
    assert body["ssl_enabled"] is True
    assert body["is_active"] is True
    assert body["policy_id"] == policy["id"]
    assert body["created_by"] == admin_user.id


def test_create_vhost_viewer_forbidden(
    client: TestClient,
    viewer_token: dict[str, str],
) -> None:
    """Viewer nie może tworzyć vhostów."""
    resp = client.post(
        "/vhosts",
        headers=viewer_token,
        json={
            "domain": "viewer.example.com",
            "backend_url": "http://localhost:3000",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_create_vhost_duplicate_domain_returns_409(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Drugi vhost z tą samą domeną -> 409."""
    _create_vhost(client, admin_token, domain="dup.example.com")

    resp = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "dup.example.com",
            "backend_url": "http://localhost:4000",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "VHost domain already exists"


def test_create_vhost_with_missing_policy_returns_404(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Nie można wskazać policy_id, które nie istnieje."""
    resp = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "missing-policy.example.com",
            "backend_url": "http://localhost:3000",
            "policy_id": 99999,
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


# ---------------------------------------------------------------------------
# GET /vhosts
# ---------------------------------------------------------------------------


def test_list_vhosts_admin_returns_200(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Admin może pobrać listę vhostów."""
    _create_vhost(client, admin_token, domain="a.example.com")
    _create_vhost(client, admin_token, domain="b.example.com")

    resp = client.get("/vhosts", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["domain"] == "a.example.com"
    assert body[1]["domain"] == "b.example.com"


def test_list_vhosts_viewer_returns_200(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Viewer ma dostęp tylko do odczytu listy."""
    _create_vhost(client, admin_token, domain="readable.example.com")

    resp = client.get("/vhosts", headers=viewer_token)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_vhosts_requires_auth(client: TestClient) -> None:
    """Brak tokena -> 401."""
    resp = client.get("/vhosts")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /vhosts/{vhost_id}
# ---------------------------------------------------------------------------


def test_get_vhost_returns_detail_with_policy(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Szczegóły vhosta zawierają zagnieżdżoną politykę."""
    policy = _create_policy(client, admin_token, name="Nested policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="detail.example.com",
        policy_id=policy["id"],
    )

    resp = client.get(f"/vhosts/{created['id']}", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["id"] == created["id"]
    assert body["domain"] == "detail.example.com"
    assert body["policy"]["id"] == policy["id"]
    assert body["policy"]["name"] == "Nested policy"


def test_get_vhost_not_found_returns_404(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Brak vhosta o danym ID -> 404."""
    resp = client.get("/vhosts/99999", headers=admin_token)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "VHost not found"


# ---------------------------------------------------------------------------
# PATCH /vhosts/{vhost_id}
# ---------------------------------------------------------------------------


def test_patch_vhost_admin_partial_update(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH aktualizuje tylko wskazane pola vhosta."""
    created = _create_vhost(
        client,
        admin_token,
        domain="patch.example.com",
        backend_url="http://localhost:3000",
        description="Before",
        ssl_enabled=False,
        is_active=True,
    )

    resp = client.patch(
        f"/vhosts/{created['id']}",
        headers=admin_token,
        json={
            "backend_url": "https://backend.internal:443",
            "ssl_enabled": True,
        },
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["domain"] == "patch.example.com"
    assert body["description"] == "Before"
    assert body["backend_url"] == "https://backend.internal:443"
    assert body["ssl_enabled"] is True
    assert body["is_active"] is True


def test_patch_vhost_viewer_forbidden(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Viewer nie może modyfikować vhosta."""
    created = _create_vhost(client, admin_token, domain="no-patch.example.com")

    resp = client.patch(
        f"/vhosts/{created['id']}",
        headers=viewer_token,
        json={"domain": "blocked.example.com"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_patch_vhost_duplicate_domain_returns_409(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Zmiana domeny na istniejącą -> 409."""
    _create_vhost(client, admin_token, domain="alpha.example.com")
    second = _create_vhost(client, admin_token, domain="beta.example.com")

    resp = client.patch(
        f"/vhosts/{second['id']}",
        headers=admin_token,
        json={"domain": "alpha.example.com"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "VHost domain already exists"


def test_patch_vhost_with_missing_policy_returns_404(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH nie pozwala przypisać nieistniejącej polityki."""
    created = _create_vhost(client, admin_token, domain="missing-patch.example.com")

    resp = client.patch(
        f"/vhosts/{created['id']}",
        headers=admin_token,
        json={"policy_id": 99999},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_patch_vhost_domain_null_returns_422(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH z domain=null powinien być odrzucony jako 422."""
    created = _create_vhost(client, admin_token, domain="null.example.com")

    resp = client.patch(
        f"/vhosts/{created['id']}",
        headers=admin_token,
        json={"domain": None},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Field 'domain' cannot be null"


def test_patch_vhost_backend_url_without_protocol_returns_422(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH musi walidować backend_url tak samo jak POST."""
    created = _create_vhost(client, admin_token, domain="invalid-url.example.com")

    resp = client.patch(
        f"/vhosts/{created['id']}",
        headers=admin_token,
        json={"backend_url": "backend.internal:443"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /vhosts/{vhost_id}
# ---------------------------------------------------------------------------


def test_delete_vhost_admin_returns_204(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Admin może usunąć vhost."""
    created = _create_vhost(client, admin_token, domain="delete.example.com")

    resp = client.delete(f"/vhosts/{created['id']}", headers=admin_token)
    assert resp.status_code == 204
    assert resp.text == ""

    get_resp = client.get(f"/vhosts/{created['id']}", headers=admin_token)
    assert get_resp.status_code == 404


def test_delete_vhost_viewer_forbidden(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Viewer nie może usuwać vhosta."""
    created = _create_vhost(client, admin_token, domain="no-delete.example.com")

    resp = client.delete(f"/vhosts/{created['id']}", headers=viewer_token)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_delete_vhost_not_found_returns_404(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """DELETE nieistniejącego vhosta -> 404."""
    resp = client.delete("/vhosts/99999", headers=admin_token)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "VHost not found"
