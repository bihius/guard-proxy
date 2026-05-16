"""Runtime operation status snapshots for generated/deployed config lifecycle."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RuntimeOperationType(enum.StrEnum):
    """Kinds of runtime operations relevant for deployment visibility."""

    validation = "validation"
    reload = "reload"


class RuntimeOperationStatus(enum.StrEnum):
    """Outcome of a runtime operation."""

    success = "success"
    failed = "failed"


class RuntimeOperation(Base):
    """Latest runtime operation snapshots used by status endpoints and dashboards."""

    __tablename__ = "runtime_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_type: Mapped[RuntimeOperationType] = mapped_column(
        Enum(RuntimeOperationType),
        nullable=False,
        index=True,
    )
    status: Mapped[RuntimeOperationStatus] = mapped_column(
        Enum(RuntimeOperationStatus),
        nullable=False,
        index=True,
    )
    config_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<RuntimeOperation id={self.id} type={self.operation_type} "
            f"status={self.status} created_at={self.created_at.isoformat()}>"
        )
