"""Log model — zdarzenia widoczne w panelu administracyjnym."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LogSeverity(enum.StrEnum):
    """Poziom ważności wpisu logu.

    StrEnum sprawia, że API zwraca zwykły string, np. "error",
    zamiast obiektu enum trudniejszego do użycia po stronie frontendu.
    """

    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class Log(Base):
    """Tabela logs — wpisy z WAF/proxy pokazywane w UI.

    Trzymamy dane zdenormalizowane:
    - vhost jako string, bo log ma być historycznym snapshotem
    - severity jako enum, żeby filtrowanie było bezpieczne i przewidywalne
    - logged_at jako czas zdarzenia, nie czas wstawienia rekordu
    """

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        server_default=func.now(),
    )
    vhost: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    severity: Mapped[LogSeverity] = mapped_column(
        Enum(LogSeverity),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Log id={self.id} vhost={self.vhost!r} "
            f"severity={self.severity} logged_at={self.logged_at.isoformat()}>"
        )
