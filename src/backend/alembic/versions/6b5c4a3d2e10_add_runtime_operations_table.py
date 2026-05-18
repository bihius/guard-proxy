"""add runtime operations table

Revision ID: 6b5c4a3d2e10
Revises: 8d4f2a6c1b90
Create Date: 2026-05-16 19:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b5c4a3d2e10"
down_revision: str | Sequence[str] | None = "8d4f2a6c1b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _runtime_operation_type_enum() -> sa.Enum:
    return sa.Enum("validation", "reload", name="runtimeoperationtype")


def _runtime_operation_status_enum() -> sa.Enum:
    return sa.Enum("success", "failed", name="runtimeoperationstatus")


def upgrade() -> None:
    """Upgrade schema."""
    context = op.get_context()
    bind = op.get_bind()

    if context.dialect.name == "postgresql":
        _runtime_operation_type_enum().create(bind, checkfirst=True)
        _runtime_operation_status_enum().create(bind, checkfirst=True)
        operation_type_enum: sa.Enum = postgresql.ENUM(
            "validation",
            "reload",
            name="runtimeoperationtype",
            create_type=False,
        )
        operation_status_enum: sa.Enum = postgresql.ENUM(
            "success",
            "failed",
            name="runtimeoperationstatus",
            create_type=False,
        )
    else:
        operation_type_enum = _runtime_operation_type_enum()
        operation_status_enum = _runtime_operation_status_enum()

    op.create_table(
        "runtime_operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operation_type", operation_type_enum, nullable=False),
        sa.Column("status", operation_status_enum, nullable=False),
        sa.Column("config_checksum", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_runtime_operations_created_at"),
        "runtime_operations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_runtime_operations_operation_type"),
        "runtime_operations",
        ["operation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_runtime_operations_status"),
        "runtime_operations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_runtime_operations_status"), table_name="runtime_operations")
    op.drop_index(
        op.f("ix_runtime_operations_operation_type"),
        table_name="runtime_operations",
    )
    op.drop_index(op.f("ix_runtime_operations_created_at"), table_name="runtime_operations")
    op.drop_table("runtime_operations")

    context = op.get_context()
    if context.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS runtimeoperationstatus")
        op.execute("DROP TYPE IF EXISTS runtimeoperationtype")
