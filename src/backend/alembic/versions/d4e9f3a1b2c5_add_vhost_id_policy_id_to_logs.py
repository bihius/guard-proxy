"""add vhost_id and policy_id FK columns to logs

Revision ID: d4e9f3a1b2c5
Revises: c7a2e5b8f1d0
Create Date: 2026-05-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e9f3a1b2c5"
down_revision: str | Sequence[str] | None = "6b5c4a3d2e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable vhost_id and policy_id FK columns with indexes."""
    with op.batch_alter_table("logs") as batch_op:
        batch_op.add_column(
            sa.Column("vhost_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("policy_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_logs_vhost_id",
            "vhosts",
            ["vhost_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_logs_policy_id",
            "policies",
            ["policy_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_logs_vhost_id", "logs", ["vhost_id"], unique=False)
    op.create_index("ix_logs_policy_id", "logs", ["policy_id"], unique=False)


def downgrade() -> None:
    """Remove vhost_id and policy_id FK columns and their indexes."""
    op.drop_index("ix_logs_policy_id", table_name="logs")
    op.drop_index("ix_logs_vhost_id", table_name="logs")
    with op.batch_alter_table("logs") as batch_op:
        batch_op.drop_constraint("fk_logs_policy_id", type_="foreignkey")
        batch_op.drop_constraint("fk_logs_vhost_id", type_="foreignkey")
        batch_op.drop_column("policy_id")
        batch_op.drop_column("vhost_id")
