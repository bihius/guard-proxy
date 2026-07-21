"""add ddos protection fields to policies

Revision ID: 473d83df7b55
Revises: b7c4d8e9f012
Create Date: 2026-07-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "473d83df7b55"
down_revision: str | Sequence[str] | None = "b7c4d8e9f012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("policies") as batch_op:
        batch_op.add_column(
            sa.Column(
                "ddos_protection_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "rate_limit_requests",
                sa.Integer(),
                nullable=False,
                server_default="100",
            )
        )
        batch_op.add_column(
            sa.Column(
                "rate_limit_window_seconds",
                sa.Integer(),
                nullable=False,
                server_default="10",
            )
        )
        batch_op.add_column(
            sa.Column(
                "max_connections_per_ip",
                sa.Integer(),
                nullable=False,
                server_default="20",
            )
        )
        batch_op.create_check_constraint(
            "ck_policies_rate_limit_requests",
            "rate_limit_requests >= 1",
        )
        batch_op.create_check_constraint(
            "ck_policies_rate_limit_window_seconds",
            "rate_limit_window_seconds BETWEEN 1 AND 3600",
        )
        batch_op.create_check_constraint(
            "ck_policies_max_connections_per_ip",
            "max_connections_per_ip >= 1",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("policies") as batch_op:
        batch_op.drop_constraint(
            "ck_policies_max_connections_per_ip", type_="check"
        )
        batch_op.drop_constraint(
            "ck_policies_rate_limit_window_seconds", type_="check"
        )
        batch_op.drop_constraint("ck_policies_rate_limit_requests", type_="check")
        batch_op.drop_column("max_connections_per_ip")
        batch_op.drop_column("rate_limit_window_seconds")
        batch_op.drop_column("rate_limit_requests")
        batch_op.drop_column("ddos_protection_enabled")
