"""Policy model — szablony konfiguracji WAF."""

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
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.rule_override import RuleOverride
    from app.models.vhost import VHost


class Policy(Base):
    """Tabela policies — szablony konfiguracji WAF.

    Polityka definiuje jak agresywnie WAF filtruje ruch:
    - paranoia_level 1 = mało fałszywych alarmów, mniej blokuje
    - paranoia_level 4 = bardzo agresywny, może blokować legalne requesty
    - anomaly_threshold = ile punktów "podejrzaności" zanim request zostanie zablokowany
    """

    __tablename__ = "policies"
    __table_args__ = (
        CheckConstraint(
            "paranoia_level BETWEEN 1 AND 4",
            name="ck_policies_paranoia_level",
        ),
        CheckConstraint(
            "anomaly_threshold >= 0",
            name="ck_policies_anomaly_threshold",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,  # unikalna nazwa polityki (np. "Strict", "Default", "Permissive")
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,  # opis jest opcjonalny
    )

    # Parametry WAF (OWASP CRS)
    paranoia_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,  # 1-4, domyślnie najmniej agresywny
    )
    anomaly_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,  # domyślny próg OWASP CRS
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Audyt — kto stworzył politykę
    # ForeignKey("users.id") = referencja do tabeli users, kolumna id
    # nullable=True — może być NULL jeśli user został usunięty (soft delete)
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

    # Relacje ORM — pozwalają robić policy.rule_overrides zamiast ręcznego JOIN
    # "RuleOverride" — nazwa klasy (string żeby uniknąć circular imports)
    # back_populates — po drugiej stronie relacji jest pole 'policy'
    # cascade="all, delete-orphan" — usuń rule_overrides gdy usuwasz policy
    rule_overrides: Mapped[list[RuleOverride]] = relationship(
        "RuleOverride",
        back_populates="policy",
        cascade="all, delete-orphan",
    )

    # Jeden policy może być przypisany do wielu vhostów
    # back_populates="policy" odpowiada polu 'policy' w modelu VHost
    vhosts: Mapped[list[VHost]] = relationship(
        "VHost",
        back_populates="policy",
    )

    def __repr__(self) -> str:
        return (
            f"<Policy id={self.id} name={self.name!r} paranoia={self.paranoia_level}>"
        )
