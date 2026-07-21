"""add auto ban fields to policies

Revision ID: ea9292cbacec
Revises: 473d83df7b55
Create Date: 2026-07-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea9292cbacec"
down_revision: str | Sequence[str] | None = "473d83df7b55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("policies") as batch_op:
        batch_op.add_column(
            sa.Column(
                "auto_ban_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "ban_threshold",
                sa.Integer(),
                nullable=False,
                server_default="10",
            )
        )
        batch_op.add_column(
            sa.Column(
                "ban_duration_seconds",
                sa.Integer(),
                nullable=False,
                server_default="600",
            )
        )
        batch_op.create_check_constraint(
            "ck_policies_ban_threshold",
            "ban_threshold >= 1",
        )
        batch_op.create_check_constraint(
            "ck_policies_ban_duration_seconds",
            "ban_duration_seconds BETWEEN 1 AND 86400",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("policies") as batch_op:
        batch_op.drop_constraint(
            "ck_policies_ban_duration_seconds", type_="check"
        )
        batch_op.drop_constraint("ck_policies_ban_threshold", type_="check")
        batch_op.drop_column("ban_duration_seconds")
        batch_op.drop_column("ban_threshold")
        batch_op.drop_column("auto_ban_enabled")
