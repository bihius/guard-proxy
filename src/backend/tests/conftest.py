"""Shared pytest fixtures for the Guard Proxy backend tests.

Architecture:
- Each test gets a fresh in-memory SQLite database (no state leaks between tests).
- The app's get_db dependency is overridden to use the test database.
- TestClient wraps the app for integration tests (synchronous, no async).
- Pre-created admin and viewer users are available as fixtures for auth tests.

Fixture hierarchy:
  engine (session-scoped) <- one engine shared across the whole test session
    └─ db (function-scoped) <- fresh transaction per test, always rolled back
         └─ client (function-scoped) <- TestClient bound to the test database
   └─ admin_user / viewer_user / inactive_user <- ORM User objects
        in the test database
        └─ admin_token / viewer_token <- Authorization headers
             with a valid JWT token
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

# JWT_SECRET_KEY must be set before any app.* import resolves Settings.
# Always force a deterministic test value so the tests stay hermetic,
# regardless of what the environment provides.
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest-onlyx"
os.environ["LOG_INGEST_SHARED_SECRET"] = "test-log-ingest-shared-secret-pytest"
os.environ["DEBUG"] = "false"

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services.auth_service import create_access_token, hash_password  # noqa: E402

# ---------------------------------------------------------------------------
# Database engine: one in-memory SQLite database for the whole test session
# ---------------------------------------------------------------------------

# connect_args keeps one connection shared across threads for the in-memory DB.
# SQLAlchemy's default pool would open a separate, empty database per connection,
# so StaticPool makes every sessionmaker call reuse the same :memory: database.
_TEST_DB_URL = "sqlite://"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """One SQLAlchemy engine bound to an in-memory SQLite database.

    Session-scoped: created once and reused for the whole test run.
    All tables are created here and dropped when the session ends.
    """
    from sqlalchemy.pool import StaticPool

    eng = create_engine(
        _TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


# ---------------------------------------------------------------------------
# Database session: a fresh transaction per test, always rolled back
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(engine: Engine) -> Iterator[Session]:
    """Isolated database session for a single test.

    Opens a connection and starts a transaction, then yields a Session bound
    to that connection. After the test, the outer transaction is rolled back,
    so no data survives between tests.
    """
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection, class_=Session, expire_on_commit=False)
    session = TestSession()

    # Enforce foreign keys in SQLite (off by default)
    session.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# TestClient: FastAPI app with the get_db dependency overridden
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db: Session) -> Iterator[TestClient]:
    """TestClient bound to the test database session.

    Overrides the get_db dependency so every request handler receives the same
    isolated session as the test. Changes made by the test are visible to the app
    and vice versa, all within the same rolled-back transaction.
    """

    def override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Pre-created users
# ---------------------------------------------------------------------------

_ADMIN_PASSWORD = "adminpassword123"
_VIEWER_PASSWORD = "viewerpassword123"
_INACTIVE_PASSWORD = "inactivepassword123"


@pytest.fixture()
def admin_user(db: Session) -> User:
    """Persisted user with the admin role, available for auth tests."""
    user = User(
        email="admin@example.com",
        hashed_password=hash_password(_ADMIN_PASSWORD),
        full_name="Test Admin",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.flush()  # assigns user.id without committing
    return user


@pytest.fixture()
def viewer_user(db: Session) -> User:
    """Persisted user with the viewer role, available for auth tests."""
    user = User(
        email="viewer@example.com",
        hashed_password=hash_password(_VIEWER_PASSWORD),
        full_name="Test Viewer",
        role=UserRole.viewer,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def inactive_user(db: Session) -> User:
    """Persisted inactive user, for testing the blocked-account path."""
    user = User(
        email="inactive@example.com",
        hashed_password=hash_password(_INACTIVE_PASSWORD),
        full_name="Inactive User",
        role=UserRole.viewer,
        is_active=False,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_token(admin_user: User) -> dict[str, str]:
    """Authorization header with a valid admin access token."""
    token = create_access_token(admin_user.id, admin_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def viewer_token(viewer_user: User) -> dict[str, str]:
    """Authorization header with a valid viewer access token."""
    token = create_access_token(viewer_user.id, viewer_user.role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Plaintext password exports: integration tests send them to POST /auth/login
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = _ADMIN_PASSWORD
VIEWER_PASSWORD = _VIEWER_PASSWORD
INACTIVE_PASSWORD = _INACTIVE_PASSWORD


@pytest.fixture()
def log_ingest_headers() -> dict[str, str]:
    """Header used by the log producer ingest endpoint."""
    return {"X-Guard-Proxy-Ingest-Secret": os.environ["LOG_INGEST_SHARED_SECRET"]}


# ---------------------------------------------------------------------------
# Rate-limiter reset — prevents counter leakage between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    """Reset slowapi in-memory counters before and after every test.

    The limiter is attached to the shared FastAPI ``app`` instance which
    survives across the entire test session.  Without this fixture, rapid
    sequences of login/refresh calls in earlier tests would exhaust the
    per-IP bucket and cause unrelated tests to see unexpected 429 responses.
    """
    from app.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def _coraza_serves_every_application(monkeypatch: pytest.MonkeyPatch) -> None:
    """No coraza-spoa runs in unit/integration tests; treat every app as loaded.

    Config apply waits for Coraza before reloading HAProxy. Tests that cover
    that wait patch `_wait_for_coraza_apps` or `_wait_for_coraza_reload`.
    """
    from app.services import config_apply

    monkeypatch.setattr(
        config_apply,
        "_wait_for_coraza_apps",
        lambda app_names: config_apply.CommandResult(ok=True, output="test"),
    )
    monkeypatch.setattr(
        config_apply,
        "_wait_for_coraza_reload",
        lambda release: config_apply.CommandResult(ok=True, output="test"),
    )
