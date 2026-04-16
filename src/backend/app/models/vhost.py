"""VHost model — domeny obsługiwane przez HAProxy."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.policy import Policy


class VHost(Base):
    """Tabela vhosts — wirtualne hosty (domeny) zarządzane przez Guard Proxy.

    Każdy vhost to jedna domena (np. example.com) która:
    - jest obsługiwana przez HAProxy (frontend → backend)
    - ma przypisaną politykę WAF (opcjonalnie)
    - może mieć włączony/wyłączony SSL

    Database invariant: the stored domain must be lowercase. API schemas
    normalize domains to lowercase and this check protects against raw SQL
    inserts/migrations that bypass schema validation.
    """

    __tablename__ = "vhosts"
    __table_args__ = (
        CheckConstraint("domain = lower(domain)", name="ck_vhosts_domain_lowercase"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Domena — musi być unikalna (nie możesz mieć dwóch vhostów na tę samą domenę)
    domain: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,  # szybkie wyszukiwanie po domenie
        nullable=False,
    )

    # URL backendu — dokąd HAProxy przekierowuje ruch
    # np. "http://localhost:3000" lub "http://192.168.1.10:8080"
    backend_url: Mapped[str] = mapped_column(String(512), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relacja do Policy — każdy vhost może mieć jedną politykę WAF
    # nullable=True — vhost może działać bez polityki (brak filtrowania WAF)
    # ondelete="SET NULL" — jeśli polityka zostanie usunięta, pole staje się NULL
    #                       (zamiast usuwać cały vhost)
    policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("policies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relacja do User — kto stworzył vhosta (audyt)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relacja ORM — policy.vhosts albo vhost.policy
    # back_populates="vhosts" odpowiada polu 'vhosts' w modelu Policy
    policy: Mapped[Policy | None] = relationship(
        "Policy",
        foreign_keys=[policy_id],
        back_populates="vhosts",
    )

    def __repr__(self) -> str:
        return f"<VHost id={self.id} domain={self.domain!r} active={self.is_active}>"
