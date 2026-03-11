"""RuleOverride model — nadpisania reguł OWASP CRS w ramach polityki WAF."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.policy import Policy


class RuleAction(enum.StrEnum):
    """Akcja nadpisania reguły CRS.

    enable  — włącz regułę (jeśli była wyłączona na niższym paranoia level)
    disable — wyłącz regułę (np. powoduje false positives w Twojej aplikacji)
    """

    enable = "enable"
    disable = "disable"


class RuleOverride(Base):
    """Tabela rule_overrides — nadpisania konkretnych reguł CRS w polityce.

    Przykład użycia:
    - Polityka "Default" ma paranoia_level=2
    - Reguła 942100 (SQL injection) powoduje false positives w Twojej apce
    - Dodajesz RuleOverride(rule_id=942100, action=disable) dla tej polityki
    - Guard Proxy wygeneruje konfigurację HAProxy z wyłączoną tą regułą
    """

    __tablename__ = "rule_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Relacja do Policy — nadpisanie należy do konkretnej polityki
    # ondelete="CASCADE" — jeśli polityka zostanie usunięta, usuń też jej nadpisania
    #                      (w przeciwieństwie do vhosts gdzie SET NULL ma sens)
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # często będziemy pytać "jakie nadpisania ma polityka X?"
    )

    # Numer reguły OWASP CRS — np. 941100 (XSS), 942100 (SQLi)
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Co zrobić z regułą
    action: Mapped[RuleAction] = mapped_column(Enum(RuleAction), nullable=False)

    # Opcjonalny komentarz — dlaczego wyłączasz/włączasz tę regułę
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relacja ORM do Policy (druga strona relacji z policy.rule_overrides)
    policy: Mapped[Policy] = relationship(  # noqa: F821
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
