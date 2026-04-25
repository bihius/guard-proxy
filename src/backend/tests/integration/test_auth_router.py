"""Testy integracyjne routera auth z refresh tokenem w HttpOnly cookie."""

from fastapi.testclient import TestClient

from app.config import settings
from app.models.user import User
from tests.conftest import ADMIN_PASSWORD, INACTIVE_PASSWORD, VIEWER_PASSWORD


def test_login_valid_admin_returns_200_and_sets_refresh_cookie(
    client: TestClient, admin_user: User
) -> None:
    resp = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": ADMIN_PASSWORD},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" not in body
    assert body["token_type"] == "bearer"
    assert settings.auth_refresh_cookie_name in resp.cookies
    assert "HttpOnly" in resp.headers["set-cookie"]


def test_login_valid_viewer_returns_200_and_sets_refresh_cookie(
    client: TestClient, viewer_user: User
) -> None:
    resp = client.post(
        "/auth/login",
        json={"email": viewer_user.email, "password": VIEWER_PASSWORD},
    )

    assert resp.status_code == 200
    assert settings.auth_refresh_cookie_name in resp.cookies


def test_login_wrong_password_returns_401(client: TestClient, admin_user: User) -> None:
    resp = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": "zle-haslo-12345"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_nonexistent_email_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/auth/login",
        json={"email": "nie@istnieje.com", "password": "jakiekolwiek12"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_inactive_user_returns_401(
    client: TestClient, inactive_user: User
) -> None:
    resp = client.post(
        "/auth/login",
        json={"email": inactive_user.email, "password": INACTIVE_PASSWORD},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_all_failure_messages_identical(
    client: TestClient, admin_user: User, inactive_user: User
) -> None:
    cases = [
        {"email": "nie@istnieje.com", "password": "jakiekolwiek12"},
        {"email": admin_user.email, "password": "zlehaslo12345"},
        {"email": inactive_user.email, "password": INACTIVE_PASSWORD},
    ]
    details = set()

    for payload in cases:
        resp = client.post("/auth/login", json=payload)
        assert resp.status_code == 401
        details.add(resp.json()["detail"])

    assert len(details) == 1


def test_login_preflight_returns_cors_headers(client: TestClient) -> None:
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert resp.headers["access-control-allow-credentials"] == "true"
    assert "POST" in resp.headers["access-control-allow-methods"]


def test_me_preflight_allows_authorization_header(client: TestClient) -> None:
    resp = client.options(
        "/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert resp.headers["access-control-allow-credentials"] == "true"
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()


def test_refresh_valid_cookie_returns_new_access_token(
    client: TestClient, admin_user: User
) -> None:
    login_resp = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": ADMIN_PASSWORD},
    )
    old_cookie = login_resp.cookies.get(settings.auth_refresh_cookie_name)

    resp = client.post("/auth/refresh")

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" not in body
    assert resp.cookies.get(settings.auth_refresh_cookie_name)
    assert resp.cookies.get(settings.auth_refresh_cookie_name) != old_cookie


def test_refresh_missing_cookie_returns_401(client: TestClient) -> None:
    resp = client.post("/auth/refresh")
    assert resp.status_code == 401


def test_refresh_invalid_cookie_returns_401(client: TestClient) -> None:
    client.cookies.set(settings.auth_refresh_cookie_name, "garbage")
    resp = client.post("/auth/refresh")
    assert resp.status_code == 401


def test_refresh_access_token_in_cookie_returns_401(
    client: TestClient, admin_user: User
) -> None:
    login_resp = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": ADMIN_PASSWORD},
    )
    access_token = login_resp.json()["access_token"]

    client.cookies.set(settings.auth_refresh_cookie_name, access_token)
    resp = client.post("/auth/refresh")
    assert resp.status_code == 401


def test_refresh_inactive_user_returns_401(
    client: TestClient, inactive_user: User
) -> None:
    from app.services.auth_service import create_refresh_token

    client.cookies.set(
        settings.auth_refresh_cookie_name,
        create_refresh_token(user_id=inactive_user.id),
    )
    resp = client.post("/auth/refresh")
    assert resp.status_code == 401


def test_refresh_nonexistent_user_returns_401(client: TestClient) -> None:
    from app.services.auth_service import create_refresh_token

    client.cookies.set(
        settings.auth_refresh_cookie_name,
        create_refresh_token(user_id=99999),
    )
    resp = client.post("/auth/refresh")
    assert resp.status_code == 401


def test_logout_clears_refresh_cookie(client: TestClient, admin_user: User) -> None:
    client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": ADMIN_PASSWORD},
    )

    resp = client.post("/auth/logout")

    assert resp.status_code == 204
    assert settings.auth_refresh_cookie_name not in client.cookies
    assert (
        "Max-Age=0" in resp.headers["set-cookie"]
        or "expires=" in resp.headers["set-cookie"].lower()
    )


def test_me_returns_user_data(
    client: TestClient, admin_user: User, admin_token: dict[str, str]
) -> None:
    resp = client.get("/auth/me", headers=admin_token)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == admin_user.email
    assert body["full_name"] == admin_user.full_name
    assert body["role"] == "admin"
    assert "hashed_password" not in body
    assert "password" not in body


def test_me_viewer_returns_viewer_role(
    client: TestClient, viewer_user: User, viewer_token: dict[str, str]
) -> None:
    resp = client.get("/auth/me", headers=viewer_token)
    assert resp.status_code == 200
    assert resp.json()["role"] == "viewer"


def test_me_no_token_returns_401(client: TestClient) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_password_not_in_response(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    resp = client.get("/auth/me", headers=admin_token)
    body = resp.json()
    assert "password" not in body
    assert "hashed_password" not in body
