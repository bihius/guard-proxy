"""User model — konta użytkowników panelu admina."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(enum.StrEnum):
    """Role użytkownika.

    Dziedziczy po str żeby JSON serializacja działała automatycznie:
    user.role → "admin" (nie UserRole.admin)
    """

    admin = "admin"
    viewer = "viewer"


class User(Base):
    """Tabela users — konta użytkowników panelu admina.

    admin  — pełny dostęp (CRUD na wszystkich zasobach)
    viewer — tylko odczyt (GET endpoints)
    """

    __tablename__ = "users"

    # Klucz główny — auto-increment integer
    id: Mapped[int] = mapped_column(primary_key=True)

    # Dane logowania
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,  # nie może być dwóch userów z tym samym emailem
        index=True,  # index = szybkie wyszukiwanie po emailu (używamy przy logowaniu)
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Dane użytkownika
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.viewer,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,  # nowy user jest aktywny od razu
    )

    # Timestamps:
    # - created_at is set by database default (server_default=func.now())
    # - updated_at uses SQLAlchemy onupdate expression on each UPDATE statement
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # automatyczna aktualizacja przy każdym UPDATE
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
