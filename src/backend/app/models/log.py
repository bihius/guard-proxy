"""SQLAlchemy models for persisted WAF and proxy log events."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.policy import Policy


class LogSeverity(enum.StrEnum):
    """Severity level assigned to an event."""

    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class LogAction(enum.StrEnum):
    """Outcome of request processing from the proxy or WAF perspective."""

    allow = "allow"
    deny = "deny"
    monitor = "monitor"


class Log(Base):
    """Historical event snapshot stored for investigation and log viewer use."""

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    producer_event_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        unique=True,
    )
    event_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        server_default=func.now(),
    )
    vhost: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[LogAction] = mapped_column(
        Enum(LogAction),
        nullable=False,
        index=True,
    )
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    request_uri: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    rule_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paranoia_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[LogSeverity] = mapped_column(
        Enum(LogSeverity),
        nullable=False,
        index=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    vhost_id: Mapped[int | None] = mapped_column(
        ForeignKey("vhosts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("policies.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Read-only — lets the API expose the policy's current name without a
    # separate lookup. No back_populates: Policy doesn't need a logs list.
    policy: Mapped["Policy | None"] = relationship("Policy", viewonly=True)

    @property
    def policy_name(self) -> str | None:
        return self.policy.name if self.policy is not None else None

    def __repr__(self) -> str:
        return (
            f"<Log id={self.id} action={self.action} "
            f"vhost={self.vhost!r} event_at={self.event_at.isoformat()}>"
        )
