"""Backend server model for virtual hosts."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.vhost import VHost


class VHostBackend(Base):
    """Backend server attached to a virtual host.

    A vhost can have multiple backend servers. HAProxy uses these rows as
    members of one load-balanced backend section.
    """

    __tablename__ = "vhost_backends"
    __table_args__ = (
        CheckConstraint(
            "health_check_interval_seconds > 0",
            name="ck_vhost_backends_health_interval_positive",
        ),
        CheckConstraint(
            "health_check_fall > 0",
            name="ck_vhost_backends_health_fall_positive",
        ),
        CheckConstraint(
            "health_check_rise > 0",
            name="ck_vhost_backends_health_rise_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vhost_id: Mapped[int] = mapped_column(
        ForeignKey("vhosts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    health_check_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    health_check_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="/",
    )
    health_check_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )
    health_check_fall: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    health_check_rise: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    vhost: Mapped[VHost] = relationship("VHost", back_populates="backends")

    def __repr__(self) -> str:
        return (
            f"<VHostBackend id={self.id} vhost_id={self.vhost_id} "
            f"url={self.url!r} active={self.is_active}>"
        )
