"""RuleExclusion model for path/target-scoped CRS rule exclusions in a WAF policy."""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.policy import Policy


class TargetType(enum.StrEnum):
    """Coraza variable a rule exclusion removes from one rule's inspection.

    Each value is the lower-cased Coraza variable name, rendered as
    `ctl:ruleRemoveTargetById=<rule>;<VARIABLE>[:<key>]`. The names must match
    exactly: removing REQUEST_URI does nothing for a rule that matched
    REQUEST_URI_RAW.
    """

    # Single-value variables: the exclusion has no key (target_value is null).
    REQUEST_URI = "request_uri"
    REQUEST_URI_RAW = "request_uri_raw"
    REQUEST_FILENAME = "request_filename"
    # Collections: the exclusion names one member (target_value is required).
    ARGS = "args"
    ARGS_NAMES = "args_names"
    REQUEST_HEADERS = "request_headers"
    REQUEST_HEADERS_NAMES = "request_headers_names"
    REQUEST_COOKIES = "request_cookies"
    REQUEST_COOKIES_NAMES = "request_cookies_names"

    @property
    def variable(self) -> str:
        """Coraza variable name, e.g. REQUEST_URI_RAW."""
        return self.value.upper()

    @property
    def takes_key(self) -> bool:
        return self not in _SINGLE_VALUE_TARGET_TYPES


_SINGLE_VALUE_TARGET_TYPES = frozenset(
    {TargetType.REQUEST_URI, TargetType.REQUEST_URI_RAW, TargetType.REQUEST_FILENAME}
)

# Characters a target value may contain so it can be written verbatim into
# generated `ctl:ruleRemoveTargetById=<id>;<VARIABLE>:<value>` syntax. Checked
# on create/update and again at config generation.
TARGET_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9_.:/@-]+$")


def target_error(target_type: TargetType, target_value: str | None) -> str | None:
    """Why this target cannot be rendered, or None when it is valid."""
    if not target_type.takes_key:
        if target_value is not None:
            return f"{target_type.variable} has no key; target value must be empty"
        return None
    if target_value is None or not target_value.strip():
        return (
            f"Target value must not be blank: {target_type.variable} needs a key, "
            "e.g. an argument name"
        )
    if not TARGET_VALUE_PATTERN.match(target_value):
        return "Target value may only contain letters, digits and _ . : / @ -"
    return None


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
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )

    # The collection member, e.g. the argument name "token". Null for
    # single-value target types (see TargetType.takes_key).
    target_value: Mapped[str | None] = mapped_column(Text, nullable=True)

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
