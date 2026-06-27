"""RuleExclusion model for path/target-scoped CRS rule exclusions in a WAF policy."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.policy import Policy


class TargetType(enum.StrEnum):
    """CRS variable a rule exclusion narrows inspection on.

    Mirrors the targets supported by SecRuleRemoveTargetById:
    REQUEST_URI, ARGS, ARGS_NAMES, REQUEST_HEADERS.
    """

    REQUEST_URI = "request_uri"
    ARGS = "args"
    ARGS_NAMES = "args_names"
    REQUEST_HEADERS = "request_headers"


class RuleExclusion(Base):
    """rule_exclusions table storing policy-specific CRS rule target exclusions.

    Example:
    - Rule 942100 (SQL injection) false-positives on the "token" argument
    - You add RuleExclusion(rule_id=942100, target_type=ARGS, target_value="token")
      scoped to scope_path="/api/login"
    - Guard Proxy can then generate config with
      SecRuleRemoveTargetById 942100 ARGS:token for that path
    """

    __tablename__ = "rule_exclusions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Relationship to Policy: every exclusion belongs to one policy.
    # ondelete="CASCADE" means exclusions are removed when the policy is deleted.
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # We often query "which exclusions belong to policy X?"
    )

    # OWASP CRS rule number, for example 941100 (XSS) or 942100 (SQLi).
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Which CRS variable to narrow inspection on.
    target_type: Mapped[TargetType] = mapped_column(Enum(TargetType), nullable=False)

    # The specific target, for example an argument name like "token".
    target_value: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional path prefix that scopes the exclusion, for example "/api/login".
    # Nullable: a missing scope_path means the exclusion applies to all paths.
    scope_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional note explaining why the exclusion exists.
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # ORM relationship back to Policy (the other side is policy.rule_exclusions).
    policy: Mapped[Policy] = relationship(
        "Policy",
        back_populates="rule_exclusions",
    )

    def __repr__(self) -> str:
        return (
            f"<RuleExclusion id={self.id} "
            f"policy_id={self.policy_id} "
            f"rule_id={self.rule_id} "
            f"target_type={self.target_type} "
            f"target_value={self.target_value}>"
        )
