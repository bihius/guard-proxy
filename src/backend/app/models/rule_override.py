"""RuleOverride model for OWASP CRS rule overrides within a WAF policy."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.policy import Policy


class RuleAction(enum.StrEnum):
    """Action applied to a CRS rule override.

    enable  — turn the rule on
    disable — turn the rule off
    """

    enable = "enable"
    disable = "disable"


class RuleOverride(Base):
    """rule_overrides table storing policy-specific CRS rule overrides.

    Example:
    - The "Default" policy has paranoia_level=2
    - Rule 942100 (SQL injection) produces false positives
    - You add RuleOverride(rule_id=942100, action=disable) for that policy
    - Guard Proxy can then generate config with that rule disabled
    """

    __tablename__ = "rule_overrides"
    __table_args__ = (
        UniqueConstraint(
            "policy_id",
            "rule_id",
            name="uq_rule_overrides_policy_id_rule_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Relationship to Policy: every override belongs to one policy.
    # ondelete="CASCADE" means overrides are removed when the policy is deleted.
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # We often query "which overrides belong to policy X?"
    )

    # OWASP CRS rule number, for example 941100 (XSS) or 942100 (SQLi).
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Desired action for that rule.
    action: Mapped[RuleAction] = mapped_column(Enum(RuleAction), nullable=False)

    # Optional note explaining why the rule is enabled or disabled.
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # ORM relationship back to Policy (the other side is policy.rule_overrides).
    policy: Mapped[Policy] = relationship(
        "Policy",
        back_populates="rule_overrides",
    )

    def __repr__(self) -> str:
        return (
            f"<RuleOverride id={self.id} "
            f"policy_id={self.policy_id} "
            f"rule_id={self.rule_id} "
            f"action={self.action}>"
        )
