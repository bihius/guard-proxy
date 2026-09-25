"""TuningSuggestion model: a proposed rule exclusion learned from WAF events (#263)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.rule_exclusion import TargetType

if TYPE_CHECKING:
    from app.models.policy import Policy


class SuggestionStatus(enum.StrEnum):
    """Review state. Suggestions are never applied without an admin approving them."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class TuningSuggestion(Base):
    """A rule exclusion the analyzer proposes for a likely false positive.

    One row per (policy, rule, target): re-running the analyzer refreshes the
    statistics of a pending row instead of adding a duplicate, and never
    re-proposes a rejected one.
    """

    __tablename__ = "tuning_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Same enum type as rule_exclusions.target_type (Postgres type "targettype").
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )
    target_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Heuristic likelihood (0-100) that the matches are false positives; see
    # app.services.tuning_analyzer.confidence_score.
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_ip_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Most recent matching log ids, for "view sample events".
    sample_log_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)

    status: Mapped[SuggestionStatus] = mapped_column(
        Enum(SuggestionStatus, name="suggestionstatus"),
        nullable=False,
        default=SuggestionStatus.pending,
    )
    # Set on approval; SET NULL keeps the audit trail if the exclusion is
    # deleted later.
    rule_exclusion_id: Mapped[int | None] = mapped_column(
        ForeignKey("rule_exclusions.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    policy: Mapped[Policy] = relationship("Policy", back_populates="tuning_suggestions")
