"""Policy model for WAF configuration templates."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.rule_override import RuleOverride
    from app.models.vhost import VHost


class Policy(Base):
    """policies table storing WAF configuration templates.

    A policy defines how aggressively WAF filters traffic:
    - paranoia_level 1 = fewer false positives, less blocking
    - paranoia_level 4 = very aggressive, may block legitimate requests
    - anomaly_threshold = how many "suspicion" points before a request is blocked
    """

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,  # unique policy name (e.g. "Strict", "Default", "Permissive")
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,  # description is optional
    )

    # WAF parameters (OWASP CRS)
    paranoia_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,  # 1-4, least aggressive by default
    )
    anomaly_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,  # default OWASP CRS threshold
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Audit — who created the policy
    # ForeignKey("users.id") = reference to users table, id column
    # nullable=True — can be NULL if the user was deleted (soft delete)
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

    # ORM relationships — lets us use policy.rule_overrides instead of manual JOIN
    # "RuleOverride" — class name as string to avoid circular imports
    # back_populates — relationship is paired with 'policy' on the other side
    # cascade="all, delete-orphan" — remove rule_overrides when deleting policy
    rule_overrides: Mapped[list[RuleOverride]] = relationship(
        "RuleOverride",
        back_populates="policy",
        cascade="all, delete-orphan",
    )

    # One policy can be assigned to many vhosts
    # back_populates="policy" matches the 'policy' field in the VHost model
    vhosts: Mapped[list[VHost]] = relationship(
        "VHost",
        back_populates="policy",
    )

    def __repr__(self) -> str:
        return (
            f"<Policy id={self.id} name={self.name!r} paranoia={self.paranoia_level}>"
        )
