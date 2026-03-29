"""Testy integracyjne routera auth (POST /auth/login, /auth/refresh, GET /auth/me).

Używamy TestClient z conftest — każdy test dostaje świeżą bazę SQLite w pamięci.
Testujemy ścieżki happy-path i błędne — bez mockowania serwisów.
"""

from fastapi.testclient import TestClient

from app.models.user import User
from tests.conftest import ADMIN_PASSWORD, INACTIVE_PASSWORD, VIEWER_PASSWORD

# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


def test_login_valid_admin_returns_200(client: TestClient, admin_user: User) -> None:
    """Poprawne dane logowania admina → 200 z tokenami."""
    resp = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_valid_viewer_returns_200(client: TestClient, viewer_user: User) -> None:
    """Poprawne dane logowania viewera → 200."""
    resp = client.post(
        "/auth/login",
        json={"email": viewer_user.email, "password": VIEWER_PASSWORD},
    )
    assert resp.status_code == 200


def test_login_wrong_password_returns_401(client: TestClient, admin_user: User) -> None:
    """Złe hasło → 401 z komunikatem 'Invalid credentials'."""
    resp = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": "zle-haslo-12345"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_nonexistent_email_returns_401(client: TestClient) -> None:
    """Email który nie istnieje w bazie → 401 (ten sam komunikat co złe hasło).

    Ważna właściwość bezpieczeństwa: atakujący nie może odróżnić złego emaila
    od złego hasła po treści odpowiedzi (brak credential confirmation).
    """
    resp = client.post(
        "/auth/login",
        json={"email": "nie@istnieje.com", "password": "jakiekolwiek12"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_inactive_user_returns_401(
    client: TestClient, inactive_user: User
) -> None:
    """Nieaktywne konto → 401 (ten sam komunikat — brak credential confirmation).

    NIE zwracamy osobnego błędu dla nieaktywnych kont — to potwierdziłoby
    atakującemu że email+hasło są poprawne.
    """
    resp = client.post(
        "/auth/login",
        json={"email": inactive_user.email, "password": INACTIVE_PASSWORD},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_all_failure_messages_identical(
    client: TestClient, admin_user: User, inactive_user: User
) -> None:
    """Wszystkie ścieżki błędu logowania zwracają identyczny komunikat."""
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
    # Wszystkie trzy przypadki muszą zwracać identyczny komunikat
    assert len(details) == 1


def test_login_preflight_returns_cors_headers(client: TestClient) -> None:
    """Preflight OPTIONS dla /auth/login powinien być obsłużony przez CORS."""
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
    assert "POST" in resp.headers["access-control-allow-methods"]


def test_me_preflight_allows_authorization_header(client: TestClient) -> None:
    """Preflight dla /auth/me powinien dopuścić nagłówek Authorization."""
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
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


def test_refresh_valid_token_returns_new_pair(
    client: TestClient, admin_user: User
) -> None:
    """Poprawny refresh token → 200 z nową parą tokenów."""
    # Najpierw logujemy się żeby dostać refresh token
    login_resp = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": ADMIN_PASSWORD},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_refresh_invalid_token_returns_401(client: TestClient) -> None:
    """Niepoprawny token → 401."""
    resp = client.post("/auth/refresh", json={"refresh_token": "garbage"})
    assert resp.status_code == 401


def test_refresh_access_token_instead_of_refresh_returns_401(
    client: TestClient, admin_user: User
) -> None:
    """Access token użyty jako refresh token → 401 (zły typ tokena)."""
    login_resp = client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": ADMIN_PASSWORD},
    )
    access_token = login_resp.json()["access_token"]

    resp = client.post("/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


def test_refresh_inactive_user_returns_401(
    client: TestClient, inactive_user: User
) -> None:
    """Refresh token użytkownika, który stał się nieaktywny → 401."""
    from app.services.auth_service import create_refresh_token

    token = create_refresh_token(user_id=inactive_user.id)
    resp = client.post("/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401


def test_refresh_nonexistent_user_returns_401(client: TestClient) -> None:
    """Refresh token z nieistniejącym user_id → 401."""
    from app.services.auth_service import create_refresh_token

    token = create_refresh_token(user_id=99999)
    resp = client.post("/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


def test_me_returns_user_data(
    client: TestClient, admin_user: User, admin_token: dict[str, str]
) -> None:
    """GET /auth/me z poprawnym tokenem → 200 z danymi usera."""
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
    """GET /auth/me dla viewera → role == 'viewer'."""
    resp = client.get("/auth/me", headers=viewer_token)
    assert resp.status_code == 200
    assert resp.json()["role"] == "viewer"


def test_me_no_token_returns_401(client: TestClient) -> None:
    """GET /auth/me bez tokena → 401."""
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_password_not_in_response(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Odpowiedź /auth/me nigdy nie zawiera hasła ani jego hasha."""
    resp = client.get("/auth/me", headers=admin_token)
    body = resp.json()
    assert "password" not in body
    assert "hashed_password" not in body
