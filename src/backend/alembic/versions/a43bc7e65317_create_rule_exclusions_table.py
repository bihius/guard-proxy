"""create rule_exclusions table

Revision ID: a43bc7e65317
Revises: 0bc86f680ecc
Create Date: 2026-06-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a43bc7e65317"
down_revision: str | Sequence[str] | None = "0bc86f680ecc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rule_exclusions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column(
            "target_type",
            sa.Enum(
                "request_uri",
                "args",
                "args_names",
                "request_headers",
                name="targettype",
            ),
            nullable=False,
        ),
        sa.Column("target_value", sa.Text(), nullable=False),
        sa.Column("scope_path", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_rule_exclusions_policy_id"),
        "rule_exclusions",
        ["policy_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_rule_exclusions_policy_id"), table_name="rule_exclusions")
    op.drop_table("rule_exclusions")

    # PostgreSQL creates enum types as separate DB objects — drop them explicitly.
    # SQLite has no native enum type, so this block must be skipped there.
    context = op.get_context()
    if context.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS targettype")
