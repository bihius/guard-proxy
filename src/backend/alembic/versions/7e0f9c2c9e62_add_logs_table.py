"""add logs table

Revision ID: 7e0f9c2c9e62
Revises: 13e761207c57
Create Date: 2026-03-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e0f9c2c9e62"
down_revision: str | Sequence[str] | None = "13e761207c57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "logged_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("vhost", sa.String(length=255), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("info", "warning", "error", "critical", name="logseverity"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_logs_logged_at"), "logs", ["logged_at"], unique=False)
    op.create_index(op.f("ix_logs_severity"), "logs", ["severity"], unique=False)
    op.create_index(op.f("ix_logs_vhost"), "logs", ["vhost"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_logs_vhost"), table_name="logs")
    op.drop_index(op.f("ix_logs_severity"), table_name="logs")
    op.drop_index(op.f("ix_logs_logged_at"), table_name="logs")
    op.drop_table("logs")

    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS logseverity")
