"""Testy integracyjne routera vhosts (CRUD + autoryzacja)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.vhost_backend import VHostBackend


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
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
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
    assert len(body["backends"]) == 1
    assert body["backends"][0]["url"] == "http://localhost:3000"
    assert body["backends"][0]["health_check_enabled"] is True
    assert len(body["policy_bindings"]) == 1
    assert body["policy_bindings"][0]["policy_id"] == policy["id"]
    assert body["policy_bindings"][0]["path_prefix"] == "/"


def test_create_vhost_with_multiple_backends_returns_201(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Admin can create a vhost backed by multiple health-checked servers."""
    resp = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "multi.example.com",
            "backends": [
                {
                    "url": "http://backend-a:8000",
                    "health_check_path": "/ready",
                    "health_check_interval_seconds": 2,
                    "health_check_fall": 2,
                    "health_check_rise": 3,
                },
                {
                    "url": "http://backend-b:8000",
                    "health_check_path": "/ready",
                },
            ],
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["backend_url"] == "http://backend-a:8000"
    assert [backend["url"] for backend in body["backends"]] == [
        "http://backend-a:8000",
        "http://backend-b:8000",
    ]
    assert body["backends"][0]["health_check_path"] == "/ready"
    assert body["backends"][0]["health_check_interval_seconds"] == 2


def test_create_vhost_rejects_mixed_health_check_paths(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """HAProxy supports one health check path per vhost backend section."""
    resp = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "mixed-health.example.com",
            "backends": [
                {
                    "url": "http://backend-a:8000",
                    "health_check_path": "/ready",
                },
                {
                    "url": "http://backend-b:8000",
                    "health_check_path": "/healthz",
                },
            ],
        },
    )

    assert resp.status_code == 400
    assert "same health_check_path" in resp.json()["detail"]


def test_create_active_vhost_rejects_all_inactive_backends(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Active vhosts must have at least one active backend."""
    resp = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "inactive-backends.example.com",
            "backends": [
                {
                    "url": "http://backend-a:8000",
                    "is_active": False,
                }
            ],
            "is_active": True,
        },
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Active vhosts require at least one active backend"


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
    """Admin can list vhosts with pagination metadata."""
    _create_vhost(client, admin_token, domain="a.example.com")
    _create_vhost(client, admin_token, domain="b.example.com")

    resp = client.get("/vhosts", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["per_page"] == 50
    assert [item["domain"] for item in body["items"]] == [
        "a.example.com",
        "b.example.com",
    ]


def test_list_vhosts_viewer_returns_200(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Viewer ma dostęp tylko do odczytu listy."""
    _create_vhost(client, admin_token, domain="readable.example.com")

    resp = client.get("/vhosts", headers=viewer_token)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


def test_list_vhosts_requires_auth(client: TestClient) -> None:
    """Brak tokena -> 401."""
    resp = client.get("/vhosts")
    assert resp.status_code == 401


def test_list_vhosts_paginates_with_page_and_per_page(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """page/per_page parameters return a slice of results."""
    for index in range(3):
        _create_vhost(client, admin_token, domain=f"host{index}.example.com")

    resp = client.get("/vhosts?page=2&per_page=2", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 2
    assert body["per_page"] == 2
    assert [item["domain"] for item in body["items"]] == ["host2.example.com"]


def test_list_vhosts_filters_by_q(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """q filters vhosts by a domain substring."""
    _create_vhost(client, admin_token, domain="app.example.com")
    _create_vhost(client, admin_token, domain="api.other.com")

    resp = client.get("/vhosts?q=example", headers=admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 1
    assert [item["domain"] for item in body["items"]] == ["app.example.com"]


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
    assert len(body["policy_bindings"]) == 1
    assert body["policy_bindings"][0]["policy_id"] == policy["id"]


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


def test_patch_vhost_replaces_backends(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH can replace the backend server list."""
    created = _create_vhost(
        client,
        admin_token,
        domain="replace-backends.example.com",
        backend_url="http://old-backend:8000",
    )

    resp = client.patch(
        f"/vhosts/{created['id']}",
        headers=admin_token,
        json={
            "backends": [
                {"url": "http://new-a:8000", "health_check_path": "/ready"},
                {
                    "url": "http://new-b:8000",
                    "health_check_enabled": False,
                },
            ]
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["backend_url"] == "http://new-a:8000"
    assert [backend["url"] for backend in body["backends"]] == [
        "http://new-a:8000",
        "http://new-b:8000",
    ]
    assert body["backends"][0]["health_check_path"] == "/ready"
    assert body["backends"][1]["health_check_enabled"] is False


def test_patch_vhost_rejects_mixed_health_check_paths(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH rejects backend lists HAProxy cannot represent correctly."""
    created = _create_vhost(
        client,
        admin_token,
        domain="mixed-patch-health.example.com",
        backend_url="http://old-backend:8000",
    )

    resp = client.patch(
        f"/vhosts/{created['id']}",
        headers=admin_token,
        json={
            "backends": [
                {"url": "http://new-a:8000", "health_check_path": "/ready"},
                {"url": "http://new-b:8000", "health_check_path": "/healthz"},
            ]
        },
    )

    assert resp.status_code == 400
    assert "same health_check_path" in resp.json()["detail"]


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


def test_patch_vhost_policy_id_updates_default_binding(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """PATCH policy_id keeps the legacy root binding synchronized."""
    first_policy = _create_policy(client, admin_token, name="First binding policy")
    second_policy = _create_policy(client, admin_token, name="Second binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="sync-binding.example.com",
        policy_id=first_policy["id"],
    )

    resp = client.patch(
        f"/vhosts/{created['id']}",
        headers=admin_token,
        json={"policy_id": second_policy["id"]},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["policy_id"] == second_policy["id"]
    assert len(body["policy_bindings"]) == 1
    assert body["policy_bindings"][0]["policy_id"] == second_policy["id"]
    assert body["policy_bindings"][0]["path_prefix"] == "/"


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
# /vhosts/{vhost_id}/policy-bindings
# ---------------------------------------------------------------------------


def test_list_policy_bindings_returns_default_binding(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Authenticated users can list a vhost's path-scoped policy bindings."""
    policy = _create_policy(client, admin_token, name="Listed binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="list-bindings.example.com",
        policy_id=policy["id"],
    )

    resp = client.get(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=viewer_token,
    )
    assert resp.status_code == 200

    body = resp.json()
    assert len(body) == 1
    assert body[0]["vhost_id"] == created["id"]
    assert body[0]["policy_id"] == policy["id"]
    assert body[0]["path_prefix"] == "/"
    assert body[0]["priority"] == 0


def test_create_policy_binding_admin_returns_201(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Admin can add a path-scoped policy binding to a vhost."""
    policy = _create_policy(client, admin_token, name="API binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="create-binding.example.com",
    )

    resp = client.post(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=admin_token,
        json={
            "policy_id": policy["id"],
            "path_prefix": "/api",
            "priority": 10,
            "comment": "API routes",
        },
    )
    assert resp.status_code == 201

    body = resp.json()
    assert body["vhost_id"] == created["id"]
    assert body["policy_id"] == policy["id"]
    assert body["path_prefix"] == "/api"
    assert body["priority"] == 10
    assert body["comment"] == "API routes"


def test_create_policy_binding_viewer_forbidden(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Viewer cannot create policy bindings."""
    policy = _create_policy(client, admin_token, name="Forbidden binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="forbidden-binding.example.com",
    )

    resp = client.post(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=viewer_token,
        json={"policy_id": policy["id"], "path_prefix": "/api", "priority": 1},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_create_policy_binding_missing_vhost_returns_404(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Creating a binding for an unknown vhost returns 404."""
    policy = _create_policy(client, admin_token, name="Missing vhost binding policy")

    resp = client.post(
        "/vhosts/99999/policy-bindings",
        headers=admin_token,
        json={"policy_id": policy["id"], "path_prefix": "/api", "priority": 1},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "VHost not found"


def test_create_policy_binding_missing_policy_returns_404(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Creating a binding with an unknown policy returns 404."""
    created = _create_vhost(
        client,
        admin_token,
        domain="missing-policy-binding.example.com",
    )

    resp = client.post(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=admin_token,
        json={"policy_id": 99999, "path_prefix": "/api", "priority": 1},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_create_policy_binding_invalid_path_returns_422(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Path prefixes must start with a slash."""
    policy = _create_policy(client, admin_token, name="Invalid path binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="invalid-path-binding.example.com",
    )

    resp = client.post(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=admin_token,
        json={"policy_id": policy["id"], "path_prefix": "api", "priority": 1},
    )
    assert resp.status_code == 422


def test_create_policy_binding_duplicate_returns_409(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """A vhost cannot have duplicate bindings for the same path and priority."""
    policy = _create_policy(client, admin_token, name="Duplicate binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="duplicate-binding.example.com",
    )
    payload = {"policy_id": policy["id"], "path_prefix": "/api", "priority": 1}
    first = client.post(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=admin_token,
        json=payload,
    )
    assert first.status_code == 201

    second = client.post(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=admin_token,
        json=payload,
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Policy binding already exists"


def test_create_policy_binding_default_root_returns_409(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """The default root binding is managed through PATCH /vhosts/{id}."""
    policy = _create_policy(client, admin_token, name="Root binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="root-binding-create.example.com",
    )

    resp = client.post(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=admin_token,
        json={"policy_id": policy["id"], "path_prefix": "/", "priority": 0},
    )
    assert resp.status_code == 409
    assert (
        resp.json()["detail"]
        == "Default root policy binding is managed through vhost.policy_id"
    )


def test_delete_policy_binding_admin_returns_204(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Admin can delete a policy binding."""
    policy = _create_policy(client, admin_token, name="Delete binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="delete-binding.example.com",
    )
    binding = client.post(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=admin_token,
        json={"policy_id": policy["id"], "path_prefix": "/api", "priority": 1},
    ).json()

    resp = client.delete(
        f"/vhosts/{created['id']}/policy-bindings/{binding['id']}",
        headers=admin_token,
    )
    assert resp.status_code == 204
    assert resp.text == ""

    list_resp = client.get(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=admin_token,
    )
    assert list_resp.status_code == 200
    assert list_resp.json() == []


def test_delete_policy_binding_default_root_returns_409(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """Deleting the default root binding directly would desync vhost.policy_id."""
    policy = _create_policy(client, admin_token, name="Root delete binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="root-binding-delete.example.com",
        policy_id=policy["id"],
    )
    root_binding = created["policy_bindings"][0]

    resp = client.delete(
        f"/vhosts/{created['id']}/policy-bindings/{root_binding['id']}",
        headers=admin_token,
    )
    assert resp.status_code == 409
    assert (
        resp.json()["detail"]
        == "Default root policy binding is managed through vhost.policy_id"
    )

    detail_resp = client.get(f"/vhosts/{created['id']}", headers=admin_token)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["policy_id"] == policy["id"]
    assert len(detail["policy_bindings"]) == 1
    assert detail["policy_bindings"][0]["id"] == root_binding["id"]


def test_delete_policy_binding_viewer_forbidden(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    """Viewer cannot delete policy bindings."""
    policy = _create_policy(client, admin_token, name="No delete binding policy")
    created = _create_vhost(
        client,
        admin_token,
        domain="no-delete-binding.example.com",
    )
    binding = client.post(
        f"/vhosts/{created['id']}/policy-bindings",
        headers=admin_token,
        json={"policy_id": policy["id"], "path_prefix": "/api", "priority": 1},
    ).json()

    resp = client.delete(
        f"/vhosts/{created['id']}/policy-bindings/{binding['id']}",
        headers=viewer_token,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


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


def test_delete_vhost_cascades_backends(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
) -> None:
    """Deleting a vhost removes its backend rows."""
    created = _create_vhost(
        client,
        admin_token,
        domain="cascade-backends.example.com",
    )
    assert db.query(VHostBackend).count() == 1

    resp = client.delete(f"/vhosts/{created['id']}", headers=admin_token)

    assert resp.status_code == 204
    assert db.query(VHostBackend).count() == 0


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


def test_create_vhost_rejects_domain_exceeding_max_length(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """A domain longer than 255 characters should be rejected with 422."""
    resp = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "a" * 256,
            "backend_url": "http://backend:8000",
        },
    )
    assert resp.status_code == 422


def test_create_vhost_rejects_backend_url_exceeding_max_length(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """A backend_url longer than 512 characters should be rejected with 422."""
    resp = client.post(
        "/vhosts",
        headers=admin_token,
        json={
            "domain": "example.com",
            "backend_url": "http://backend.internal/" + "a" * 512,
        },
    )
    assert resp.status_code == 422


def test_patch_vhost_rejects_domain_exceeding_max_length(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    """A domain PATCH longer than 255 characters should be rejected with 422."""
    created = _create_vhost(client, admin_token, domain="update-length.example.com")

    resp = client.patch(
        f"/vhosts/{created['id']}",
        headers=admin_token,
        json={"domain": "b" * 256},
    )
    assert resp.status_code == 422
