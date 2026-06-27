"""PolicyBinding model for path-scoped policy assignments on vhosts."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.policy import Policy
    from app.models.vhost import VHost


class PolicyBinding(Base):
    """Path-scoped link between a vhost and a WAF policy."""

    __tablename__ = "policy_bindings"
    __table_args__ = (
        CheckConstraint(
            "path_prefix LIKE '/%'",
            name="ck_policy_bindings_path_prefix_starts_with_slash",
        ),
        CheckConstraint(
            "priority >= 0",
            name="ck_policy_bindings_priority_non_negative",
        ),
        UniqueConstraint(
            "vhost_id",
            "path_prefix",
            "priority",
            name="uq_policy_bindings_vhost_path_priority",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    vhost_id: Mapped[int] = mapped_column(
        ForeignKey("vhosts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path_prefix: Mapped[str] = mapped_column(String(512), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    vhost: Mapped[VHost] = relationship(
        "VHost",
        back_populates="policy_bindings",
    )
    policy: Mapped[Policy] = relationship(
        "Policy",
        back_populates="policy_bindings",
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyBinding id={self.id} "
            f"vhost_id={self.vhost_id} "
            f"policy_id={self.policy_id} "
            f"path_prefix={self.path_prefix!r} "
            f"priority={self.priority}>"
        )
