"""create policy_bindings table

Revision ID: 5e2d7c9a1b34
Revises: 7da7bf17f2b8
Create Date: 2026-06-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5e2d7c9a1b34"
down_revision: str | Sequence[str] | None = "7da7bf17f2b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "policy_bindings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vhost_id", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("path_prefix", sa.String(length=512), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "path_prefix LIKE '/%'",
            name="ck_policy_bindings_path_prefix_starts_with_slash",
        ),
        sa.CheckConstraint(
            "priority >= 0",
            name="ck_policy_bindings_priority_non_negative",
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vhost_id"], ["vhosts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vhost_id",
            "path_prefix",
            "priority",
            name="uq_policy_bindings_vhost_path_priority",
        ),
    )
    op.create_index(
        op.f("ix_policy_bindings_policy_id"),
        "policy_bindings",
        ["policy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_bindings_vhost_id"),
        "policy_bindings",
        ["vhost_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO policy_bindings (
            vhost_id,
            policy_id,
            path_prefix,
            priority,
            comment
        )
        SELECT
            id,
            policy_id,
            '/',
            0,
            'Migrated from vhost.policy_id'
        FROM vhosts
        WHERE policy_id IS NOT NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_policy_bindings_vhost_id"), table_name="policy_bindings")
    op.drop_index(op.f("ix_policy_bindings_policy_id"), table_name="policy_bindings")
    op.drop_table("policy_bindings")
