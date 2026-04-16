"""User model for admin panel user accounts."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(enum.StrEnum):
    """User roles.

    Inherits from ``str`` so JSON serialization works automatically:
    user.role -> "admin" (not UserRole.admin)
    """

    admin = "admin"
    viewer = "viewer"


class User(Base):
    """users table storing admin panel user accounts.

    admin  — full access (CRUD on all resources)
    viewer — read-only access (GET endpoints)
    """

    __tablename__ = "users"

    # Primary key — auto-increment integer
    id: Mapped[int] = mapped_column(primary_key=True)

    # Login credentials
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,  # two users cannot share the same email
        index=True,  # index = fast email lookup (used during login)
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Profile data
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.viewer,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,  # new users are active by default
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
        onupdate=func.now(),  # automatically updated on every UPDATE
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
