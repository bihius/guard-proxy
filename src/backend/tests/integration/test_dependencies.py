"""Integration tests for FastAPI dependencies (get_current_user, require_admin).

Uses TestClient from conftest; each test gets a fresh in-memory SQLite database.
Tests HTTP behaviour: status codes and error bodies.
"""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.models.user import User

# ---------------------------------------------------------------------------
# get_current_user — missing header
# ---------------------------------------------------------------------------


def test_me_no_token_returns_401(client: TestClient) -> None:
    """No Authorization header → 401."""
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_invalid_token_returns_401(client: TestClient) -> None:
    """Random string as token → 401."""
    resp = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_me_expired_token_returns_401(client: TestClient, admin_user: User) -> None:
    """Expired token → 401."""
    payload = {
        "sub": str(admin_user.id),
        "role": admin_user.role,
        "type": "access",
        "exp": datetime.now(UTC) - timedelta(seconds=1),
    }
    expired = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_me_nonexistent_user_returns_401(client: TestClient) -> None:
    """Token with a non-existent user_id → 401."""
    from app.services.auth_service import create_access_token

    token = create_access_token(user_id=99999, role="admin")
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_me_inactive_user_returns_403(client: TestClient, inactive_user: User) -> None:
    """Inactive account → 403 (not 401, because the token itself is valid)."""
    from app.services.auth_service import create_access_token

    token = create_access_token(user_id=inactive_user.id, role=inactive_user.role)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_me_valid_token_returns_200(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Valid token of an active user → 200."""
    resp = client.get("/auth/me", headers=admin_token)
    assert resp.status_code == 200


def test_me_refresh_token_as_access_returns_401(
    client: TestClient, admin_user: User
) -> None:
    """Refresh token used as access token → 401."""
    from app.services.auth_service import create_refresh_token

    token = create_refresh_token(user_id=admin_user.id)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# require_admin
# ---------------------------------------------------------------------------
# require_admin has no endpoint of its own in the current router.
# We test it through a temporary test endpoint mounted per test,
# because no existing endpoint uses require_admin.
# ---------------------------------------------------------------------------


def test_require_admin_rejects_viewer(
    client: TestClient, viewer_token: dict[str, str]
) -> None:
    """Viewer with require_admin → 403.

    Mounts a temporary test endpoint for the duration of the test.
    """
    from fastapi import Depends

    from app.dependencies import require_admin
    from app.main import app
    from app.models.user import User as UserModel

    @app.get("/test-admin-only")
    def _test_endpoint(user: UserModel = Depends(require_admin)) -> dict[str, str]:
        return {"ok": "true"}

    try:
        resp = client.get("/test-admin-only", headers=viewer_token)
        assert resp.status_code == 403
        assert "Admin role required" in resp.json()["detail"]
    finally:
        # Remove the test endpoint so it does not leak into other tests
        app.routes[:] = [
            r for r in app.routes if getattr(r, "path", None) != "/test-admin-only"
        ]


def test_require_admin_accepts_admin(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Admin with require_admin → 200."""
    from fastapi import Depends

    from app.dependencies import require_admin
    from app.main import app
    from app.models.user import User as UserModel

    @app.get("/test-admin-only-2")
    def _test_endpoint(user: UserModel = Depends(require_admin)) -> dict[str, str]:
        return {"ok": "true"}

    try:
        resp = client.get("/test-admin-only-2", headers=admin_token)
        assert resp.status_code == 200
    finally:
        app.routes[:] = [
            r for r in app.routes if getattr(r, "path", None) != "/test-admin-only-2"
        ]
