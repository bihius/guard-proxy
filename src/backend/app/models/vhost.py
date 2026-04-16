"""VHost model for domains served by HAProxy."""

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
    """vhosts table for virtual hosts (domains) managed by Guard Proxy.

    Each vhost is one domain (e.g. example.com) that:
    - is served by HAProxy (frontend -> backend)
    - can have an assigned WAF policy (optional)
    - can have SSL enabled or disabled
    Database invariant: the stored domain must be lowercase. API schemas
    normalize domains to lowercase and this check protects against raw SQL
    inserts/migrations that bypass schema validation.
    """

    __tablename__ = "vhosts"
    __table_args__ = (
        CheckConstraint("domain = lower(domain)", name="ck_vhosts_domain_lowercase"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Domain — must be unique (no duplicate vhosts for the same domain)
    domain: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,  # fast domain lookup
        nullable=False,
    )

    # Backend URL — where HAProxy forwards traffic
    # e.g. "http://localhost:3000" or "http://192.168.1.10:8080"
    backend_url: Mapped[str] = mapped_column(String(512), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationship to Policy — each vhost can have one WAF policy
    # nullable=True — vhost can operate without a policy (no WAF filtering)
    # ondelete="SET NULL" — if the policy is deleted, this field becomes NULL
    #                       (instead of deleting the entire vhost)
    policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("policies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationship to User — who created the vhost (audit)
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

    # ORM relationship — policy.vhosts or vhost.policy
    # back_populates="vhosts" matches the 'vhosts' field in the Policy model
    policy: Mapped[Policy | None] = relationship(
        "Policy",
        foreign_keys=[policy_id],
        back_populates="vhosts",
    )

    def __repr__(self) -> str:
        return f"<VHost id={self.id} domain={self.domain!r} active={self.is_active}>"
