"""Testy integracyjne routera auth z refresh tokenem w HttpOnly cookie."""

from fastapi.testclient import TestClient

from app.config import settings
from app.models.user import User
from app.rate_limit import REFRESH_RATE_LIMIT
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
    assert f"Path={settings.auth_refresh_cookie_path}" in resp.headers["set-cookie"]


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


def test_preflight_does_not_advertise_wildcard_methods(client: TestClient) -> None:
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    allowed_methods = resp.headers["access-control-allow-methods"]
    assert "*" not in allowed_methods
    assert {m.strip() for m in allowed_methods.split(",")} == {
        "GET",
        "POST",
        "PATCH",
        "DELETE",
        "OPTIONS",
    }


def test_preflight_does_not_advertise_wildcard_headers(client: TestClient) -> None:
    resp = client.options(
        "/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    allowed_headers = resp.headers["access-control-allow-headers"].lower()
    assert "*" not in allowed_headers
    # Starlette's CORSMiddleware always unions allow_headers with the
    # CORS-safelisted headers (Accept, Accept-Language, Content-Language,
    # Content-Type), so those appear even though we only configured
    # Authorization and Content-Type explicitly.
    assert {h.strip() for h in allowed_headers.split(",")} == {
        "accept",
        "accept-language",
        "content-language",
        "content-type",
        "authorization",
    }


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


# ---------------------------------------------------------------------------
# Rate limiting — M0-08
# ---------------------------------------------------------------------------


def test_login_rate_limited_after_five_attempts(
    client: TestClient, admin_user: User
) -> None:
    """Six rapid login attempts from the same IP hit 429 on the sixth.

    Wrong passwords are used so the bcrypt timing cost is still incurred and
    the test does not accidentally create valid sessions, but the rate limit
    counts *all* attempts regardless of outcome.
    TestClient connects directly (no HAProxy), so the key is the loopback
    address; the autouse ``_reset_rate_limiter`` fixture ensures a clean
    counter at the start of this test.
    """
    for i in range(5):
        resp = client.post(
            "/auth/login",
            json={"email": admin_user.email, "password": "wrong-password"},
        )
        assert resp.status_code == 401, (
            f"attempt {i + 1}: expected 401, got {resp.status_code}"
        )

    sixth = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": "wrong-password"},
    )
    assert sixth.status_code == 429
    assert "retry-after" in sixth.headers
    assert "detail" in sixth.json()


def test_refresh_not_rate_limited_at_login_threshold(client: TestClient) -> None:
    """Refresh tolerates more requests than the strict login limit.

    The frontend calls ``/auth/refresh`` automatically on every page load (twice
    under React StrictMode in dev), so it must not share login's 5/minute
    brute-force ceiling. Ten rapid refreshes — well past the login limit — must
    never be rate-limited, otherwise normal reloads would bounce the user to the
    login page with a 429.
    """
    for i in range(10):
        resp = client.post("/auth/refresh")
        assert resp.status_code != 429, (
            f"attempt {i + 1} unexpectedly rate-limited"
        )


def test_refresh_eventually_rate_limited(client: TestClient) -> None:
    """Refresh is still bounded — exceeding its own limit returns 429.

    The endpoint rotates the refresh token on each successful call, so it keeps
    a generous-but-finite ceiling. Sending one request beyond REFRESH_RATE_LIMIT
    from the same IP trips the limiter.
    """
    limit = int(REFRESH_RATE_LIMIT.split("/")[0])

    for _ in range(limit):
        client.post("/auth/refresh")

    over_limit = client.post("/auth/refresh")
    assert over_limit.status_code == 429
    assert "retry-after" in over_limit.headers
    assert "detail" in over_limit.json()


def test_login_under_limit_is_not_rate_limited(
    client: TestClient, admin_user: User
) -> None:
    """Exactly five attempts do not trigger rate limiting (boundary check)."""
    for i in range(5):
        resp = client.post(
            "/auth/login",
            json={"email": admin_user.email, "password": "wrong-password"},
        )
        assert resp.status_code != 429, f"attempt {i + 1} unexpectedly rate-limited"


def test_login_rate_limit_is_per_ip(client: TestClient, admin_user: User) -> None:
    """Rate-limit buckets are keyed per client IP via X-Forwarded-For.

    Five requests from 10.0.0.1 exhaust that IP's bucket. The sixth from
    10.0.0.1 is rate-limited, but the first request from 10.0.0.2 is not —
    proving independent per-IP counters and that the XFF key function works.
    """
    ip_a = "10.0.0.1"
    ip_b = "10.0.0.2"

    for i in range(5):
        resp = client.post(
            "/auth/login",
            json={"email": admin_user.email, "password": "wrong-password"},
            headers={"X-Forwarded-For": ip_a},
        )
        assert resp.status_code == 401, (
            f"attempt {i + 1} from {ip_a}: expected 401, got {resp.status_code}"
        )

    # 6th from ip_a must be blocked
    sixth = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": "wrong-password"},
        headers={"X-Forwarded-For": ip_a},
    )
    assert sixth.status_code == 429, (
        f"expected 429 from {ip_a}, got {sixth.status_code}"
    )

    # 1st from ip_b must NOT be blocked
    first_b = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": "wrong-password"},
        headers={"X-Forwarded-For": ip_b},
    )
    assert first_b.status_code == 401, (
        f"expected 401 from {ip_b}, got {first_b.status_code}"
    )
