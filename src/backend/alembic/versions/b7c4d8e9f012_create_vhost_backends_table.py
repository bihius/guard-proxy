"""Create vhost backends table.

Revision ID: b7c4d8e9f012
Revises: 5e2d7c9a1b34
Create Date: 2026-06-29 20:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c4d8e9f012"
down_revision: str | None = "5e2d7c9a1b34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vhost_backends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vhost_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("health_check_enabled", sa.Boolean(), nullable=False),
        sa.Column("health_check_path", sa.String(length=255), nullable=False),
        sa.Column("health_check_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("health_check_fall", sa.Integer(), nullable=False),
        sa.Column("health_check_rise", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "health_check_interval_seconds > 0",
            name="ck_vhost_backends_health_interval_positive",
        ),
        sa.CheckConstraint(
            "health_check_fall > 0",
            name="ck_vhost_backends_health_fall_positive",
        ),
        sa.CheckConstraint(
            "health_check_rise > 0",
            name="ck_vhost_backends_health_rise_positive",
        ),
        sa.ForeignKeyConstraint(["vhost_id"], ["vhosts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vhost_backends_vhost_id"),
        "vhost_backends",
        ["vhost_id"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO vhost_backends (
            vhost_id,
            url,
            is_active,
            health_check_enabled,
            health_check_path,
            health_check_interval_seconds,
            health_check_fall,
            health_check_rise
        )
        SELECT
            id,
            backend_url,
            true,
            true,
            '/',
            5,
            3,
            2
        FROM vhosts
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_vhost_backends_vhost_id"), table_name="vhost_backends")
    op.drop_table("vhost_backends")
