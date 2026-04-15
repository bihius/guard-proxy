"""redesign logs table for event model

Revision ID: c7a2e5b8f1d0
Revises: 7e0f9c2c9e62
Create Date: 2026-04-11 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7a2e5b8f1d0"
down_revision: Union[str, Sequence[str], None] = "7e0f9c2c9e62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # MVP note: this intentionally rebuilds the table instead of preserving old rows.
    # The previous logs schema was a short-lived placeholder and current project
    # scope does not require retaining existing historical data yet.
    op.drop_index(op.f("ix_logs_vhost"), table_name="logs")
    op.drop_index(op.f("ix_logs_severity"), table_name="logs")
    op.drop_index(op.f("ix_logs_logged_at"), table_name="logs")
    op.drop_table("logs")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS logseverity")

    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("producer_event_id", sa.String(length=128), nullable=True),
        sa.Column(
            "event_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("vhost", sa.String(length=255), nullable=False),
        sa.Column(
            "action",
            sa.Enum("allow", "deny", "monitor", name="logaction"),
            nullable=False,
        ),
        sa.Column("source_ip", sa.String(length=45), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("request_uri", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("rule_message", sa.Text(), nullable=True),
        sa.Column("anomaly_score", sa.Integer(), nullable=True),
        sa.Column("paranoia_level", sa.Integer(), nullable=True),
        sa.Column(
            "severity",
            sa.Enum("info", "warning", "error", "critical", name="logseverity"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("raw_context", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("producer_event_id", name="uq_logs_producer_event_id"),
    )
    op.create_index(op.f("ix_logs_action"), "logs", ["action"], unique=False)
    op.create_index(op.f("ix_logs_event_at"), "logs", ["event_at"], unique=False)
    op.create_index(op.f("ix_logs_rule_id"), "logs", ["rule_id"], unique=False)
    op.create_index(op.f("ix_logs_severity"), "logs", ["severity"], unique=False)
    op.create_index(op.f("ix_logs_source_ip"), "logs", ["source_ip"], unique=False)
    op.create_index(op.f("ix_logs_vhost"), "logs", ["vhost"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_logs_vhost"), table_name="logs")
    op.drop_index(op.f("ix_logs_source_ip"), table_name="logs")
    op.drop_index(op.f("ix_logs_severity"), table_name="logs")
    op.drop_index(op.f("ix_logs_rule_id"), table_name="logs")
    op.drop_index(op.f("ix_logs_event_at"), table_name="logs")
    op.drop_index(op.f("ix_logs_action"), table_name="logs")
    op.drop_table("logs")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS logaction")
        op.execute("DROP TYPE IF EXISTS logseverity")

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
