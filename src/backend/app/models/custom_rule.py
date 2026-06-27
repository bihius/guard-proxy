"""CustomRule model for policy-scoped custom CRS rules in a WAF policy."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.policy import Policy

# Rule IDs reserved for administrator-authored custom rules, kept clear of the
# OWASP CRS range (CRS uses 900000-999999) so custom rules never collide.
CUSTOM_RULE_ID_MIN = 9000000
CUSTOM_RULE_ID_MAX = 9099999


class RulePhase(enum.StrEnum):
    """ModSecurity/Coraza processing phase a custom rule runs in.

    Mirrors the five SecRule phases (request headers/body, response
    headers/body, logging). The config generator maps these to the numeric
    phases 1-5 expected by Coraza.
    """

    REQUEST_HEADERS = "request_headers"
    REQUEST_BODY = "request_body"
    RESPONSE_HEADERS = "response_headers"
    RESPONSE_BODY = "response_body"
    LOGGING = "logging"


class RuleOperator(enum.StrEnum):
    """Coraza operator used to match the rule's variables.

    A focused MVP subset of operators supported by SecRule, for example
    @rx for regular expressions or @streq for an exact string match.
    """

    RX = "rx"
    STREQ = "streq"
    CONTAINS = "contains"
    BEGINS_WITH = "begins_with"
    ENDS_WITH = "ends_with"
    EQ = "eq"
    GE = "ge"
    GT = "gt"
    LE = "le"
    LT = "lt"
    PM = "pm"
    WITHIN = "within"
    IP_MATCH = "ip_match"


class CustomRule(Base):
    """custom_rules table storing policy-specific administrator-authored rules.

    Example:
    - You add CustomRule(rule_id=9000001, phase=REQUEST_HEADERS,
      variables="REQUEST_HEADERS:User-Agent", operator=RX,
      operator_argument="(?i)curl", actions="deny,status:403")
    - Guard Proxy can then generate config with
      SecRule REQUEST_HEADERS:User-Agent "@rx (?i)curl"
      "id:9000001,phase:1,deny,status:403"
    """

    __tablename__ = "custom_rules"
    __table_args__ = (
        CheckConstraint(
            f"rule_id >= {CUSTOM_RULE_ID_MIN} AND rule_id <= {CUSTOM_RULE_ID_MAX}",
            name="ck_custom_rules_rule_id_range",
        ),
        UniqueConstraint(
            "policy_id",
            "rule_id",
            name="uq_custom_rules_policy_id_rule_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Relationship to Policy: every custom rule belongs to one policy.
    # ondelete="CASCADE" means custom rules are removed when the policy is deleted.
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # We often query "which custom rules belong to policy X?"
    )

    # User-defined rule number, restricted to CUSTOM_RULE_ID_MIN-CUSTOM_RULE_ID_MAX
    # so custom rules never collide with OWASP CRS rule IDs.
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Which SecRule processing phase the rule runs in.
    phase: Mapped[RulePhase] = mapped_column(Enum(RulePhase), nullable=False)

    # CRS variables to inspect, for example "ARGS|REQUEST_HEADERS:User-Agent".
    variables: Mapped[str] = mapped_column(Text, nullable=False)

    # Operator used to match the variables, for example "rx" or "streq".
    operator: Mapped[RuleOperator] = mapped_column(Enum(RuleOperator), nullable=False)

    # The operator's pattern/value, for example the regex used with "@rx".
    operator_argument: Mapped[str] = mapped_column(Text, nullable=False)

    # Comma-separated SecRule actions, for example "deny,status:403,log".
    actions: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional note explaining why the rule exists.
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Whether the rule is currently enabled. Inactive rules are kept but not
    # rendered into generated config.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # ORM relationship back to Policy (the other side is policy.custom_rules).
    policy: Mapped[Policy] = relationship(
        "Policy",
        back_populates="custom_rules",
    )

    def __repr__(self) -> str:
        return (
            f"<CustomRule id={self.id} "
            f"policy_id={self.policy_id} "
            f"rule_id={self.rule_id} "
            f"phase={self.phase} "
            f"is_active={self.is_active}>"
        )
