"""Wspólne fixtures pytest dla testów backendu Guard Proxy.

Architektura:
- Każdy test dostaje świeżą bazę SQLite w pamięci (brak wycieku stanu między testami).
- Zależność get_db aplikacji FastAPI jest nadpisana, żeby używać testowej bazy danych.
- TestClient owija aplikację dla testów integracyjnych (synchroniczny, bez async).
- Wstępnie utworzeni użytkownicy admin i viewer są dostępni jako fixtures
  dla testów auth.

Hierarchia fixtures:
  engine (session-scoped) ← jeden silnik współdzielony przez całą sesję testów
    └─ db (function-scoped) ← świeża transakcja per test, zawsze rollbackowana po teście
         └─ client (function-scoped) ← TestClient podpięty do testowej bazy
  └─ admin_user / viewer_user / inactive_user ← obiekty ORM User
       w testowej bazie
       └─ admin_token / viewer_token ← nagłówki Authorization
            z ważnym tokenem JWT
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# JWT_SECRET_KEY musi być ustawiony zanim jakikolwiek import app.* rozwiąże Settings.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-onlyx")

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services.auth_service import create_access_token, hash_password  # noqa: E402

# ---------------------------------------------------------------------------
# Silnik bazy danych — jedna baza SQLite w pamięci na całą sesję testów
# ---------------------------------------------------------------------------

# connect_args utrzymuje to samo połączenie przez wszystkie wątki (pytest używa
# jednego wątku, ale pula połączeń SQLAlchemy normalnie otworzyłaby nowy plik).
# StaticPool zapewnia że każde wywołanie sessionmaker reużywa tej samej bazy :memory:.
_TEST_DB_URL = "sqlite://"


@pytest.fixture(scope="session")
def engine():
    """Jeden silnik SQLAlchemy podpięty pod bazę SQLite w pamięci.

    Session-scoped: tworzony raz i reużywany przez cały przebieg testów.
    Wszystkie tabele są tworzone tutaj i usuwane po zakończeniu sesji.
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
# Sesja bazy danych — świeża transakcja per test, zawsze rollbackowana
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(engine: Session) -> Session:
    """Izolowana sesja bazy danych dla pojedynczego testu.

    Otwiera połączenie i rozpoczyna transakcję, potem zwraca Session powiązaną
    z tym połączeniem. Po teście zewnętrzna transakcja jest rollbackowana —
    żadne dane nie zostają między testami.
    """
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection, class_=Session, expire_on_commit=False)
    session = TestSession()

    # Wymuszenie kluczy obcych w SQLite (domyślnie wyłączone)
    session.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# TestClient — aplikacja FastAPI z nadpisaną zależnością get_db
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db: Session) -> TestClient:
    """TestClient FastAPI podpięty pod testową sesję bazy danych.

    Nadpisuje zależność get_db, żeby każdy handler requestu dostał tę samą
    izolowaną sesję co test — zmiany w testach są widoczne dla aplikacji
    i odwrotnie, wszystko w ramach tej samej rollbackowanej transakcji.
    """

    def override_get_db():  # type: ignore[return]
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Wstępnie utworzeni użytkownicy
# ---------------------------------------------------------------------------

_ADMIN_PASSWORD = "adminpassword123"
_VIEWER_PASSWORD = "viewerpassword123"
_INACTIVE_PASSWORD = "inactivepassword123"


@pytest.fixture()
def admin_user(db: Session) -> User:
    """Zapisany użytkownik z rolą admin — dostępny dla testów auth."""
    user = User(
        email="admin@example.com",
        hashed_password=hash_password(_ADMIN_PASSWORD),
        full_name="Test Admin",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.flush()  # przypisuje user.id bez commita
    return user


@pytest.fixture()
def viewer_user(db: Session) -> User:
    """Zapisany użytkownik z rolą viewer — dostępny dla testów auth."""
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
    """Zapisany nieaktywny użytkownik — do testowania ścieżki zablokowanego konta."""
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
# Nagłówki auth
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_token(admin_user: User) -> dict[str, str]:
    """Nagłówek Authorization z ważnym tokenem access admina."""
    token = create_access_token(admin_user.id, admin_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def viewer_token(viewer_user: User) -> dict[str, str]:
    """Nagłówek Authorization z ważnym tokenem access viewera."""
    token = create_access_token(viewer_user.id, viewer_user.role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Eksport haseł w plaintext — testy integracyjne używają ich w POST /auth/login
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = _ADMIN_PASSWORD
VIEWER_PASSWORD = _VIEWER_PASSWORD
INACTIVE_PASSWORD = _INACTIVE_PASSWORD
